"""RAG pipeline: query → retrieve → rerank → generate (with streaming)."""

import asyncio
import time
from typing import AsyncGenerator, Optional

import structlog

from src.config import settings
from src.vector_store import build_bm25_index, hybrid_search, rerank

logger = structlog.get_logger(__name__)


# ─── LLM Providers ────────────────────────────────────────────────────────────

class LLMProvider:
    async def generate_stream(
        self, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    async def generate(self, messages: list[dict], **kwargs) -> str:
        chunks = []
        async for chunk in self.generate_stream(messages, **kwargs):
            chunks.append(chunk)
        return "".join(chunks)


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6") -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model

    async def generate_stream(
        self, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str, None]:
        import anthropic

        system = kwargs.pop("system", None)
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", 2048)

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        create_kwargs = {
            "model": self.model,
            "messages": [m for m in messages if m["role"] != "system"],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            create_kwargs["system"] = system
        else:
            sys_msgs = [m["content"] for m in messages if m["role"] == "system"]
            if sys_msgs:
                create_kwargs["system"] = "\n\n".join(sys_msgs)

        async with client.messages.stream(**create_kwargs) as stream:
            async for text in stream.text_stream:
                yield text


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o") -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model

    async def generate_stream(
        self, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI

        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", 2048)

        client = AsyncOpenAI(api_key=self.api_key)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key or settings.google_api_key
        self.model = model

    async def generate_stream(
        self, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str, None]:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", 2048)

        model = genai.GenerativeModel(
            self.model,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        # Convert messages to Gemini format
        history = []
        system_content = ""
        for m in messages:
            if m["role"] == "system":
                system_content = m["content"]
            elif m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                history.append({"role": "model", "parts": [m["content"]]})

        prompt = history[-1]["parts"][0] if history else ""
        chat_history = history[:-1]

        if system_content and chat_history:
            chat_history[0]["parts"][0] = system_content + "\n\n" + chat_history[0]["parts"][0]

        chat = model.start_chat(history=chat_history)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: chat.send_message(prompt, stream=True)
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "", model: str = "llama3.2") -> None:
        self.base_url = base_url or settings.ollama_base_url
        self.model = model

    async def generate_stream(
        self, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str, None]:
        import httpx

        temperature = kwargs.pop("temperature", 0.7)

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": temperature},
                },
            ) as response:
                response.raise_for_status()
                import json
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except Exception:
                            pass


_llm_providers: dict[str, LLMProvider] = {}


def get_llm_provider(provider: str, model: str) -> LLMProvider:
    key = f"{provider}:{model}"
    if key not in _llm_providers:
        if provider == "anthropic":
            _llm_providers[key] = AnthropicProvider(model=model)
        elif provider == "openai":
            _llm_providers[key] = OpenAIProvider(model=model)
        elif provider == "google":
            _llm_providers[key] = GeminiProvider(model=model)
        elif provider == "ollama":
            _llm_providers[key] = OllamaProvider(model=model)
        else:
            _llm_providers[key] = AnthropicProvider(model="claude-sonnet-4-6")
    return _llm_providers[key]


# ─── Query Expansion ──────────────────────────────────────────────────────────

async def expand_query(query: str, provider: LLMProvider) -> list[str]:
    """Generate query variations for multi-query retrieval."""
    prompt = f"""Generate 2 alternative search queries for this question to improve document retrieval.
Output ONLY the queries, one per line, no numbering or explanation.

Original query: {query}"""

    try:
        response = await provider.generate(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.5,
        )
        alternatives = [line.strip() for line in response.strip().split("\n") if line.strip()]
        return [query] + alternatives[:2]
    except Exception:
        return [query]


# ─── Context Building ─────────────────────────────────────────────────────────

def build_context(hits: list[dict], max_chars: int = 6000) -> tuple[str, list[dict]]:
    """Build context string and source list from search hits."""
    context_parts = []
    sources = []
    total_chars = 0

    for i, hit in enumerate(hits):
        content = hit["content"]
        if total_chars + len(content) > max_chars:
            break

        source = {
            "index": i + 1,
            "document_id": hit.get("metadata", {}).get("document_id", ""),
            "document_name": hit.get("metadata", {}).get("filename") or hit.get("metadata", {}).get("source_url", "Unknown"),
            "chunk_index": hit.get("metadata", {}).get("chunk_index", 0),
            "content": content[:200] + "..." if len(content) > 200 else content,
            "score": round(hit.get("score", 0.0), 3),
        }
        sources.append(source)
        context_parts.append(f"[Source {i+1}: {source['document_name']}]\n{content}")
        total_chars += len(content)

    return "\n\n---\n\n".join(context_parts), sources


# ─── RAG Pipeline ─────────────────────────────────────────────────────────────

async def rag_answer_stream(
    project_id: str,
    query: str,
    conversation_history: list[dict],
    system_prompt: Optional[str],
    llm_provider: str,
    llm_model: str,
    embedding_provider: str,
    embedding_model: str,
    max_context_chunks: int = 5,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    expand_queries: bool = True,
) -> tuple[AsyncGenerator[str, None], list[dict], int]:
    """
    Full RAG pipeline.
    Returns (stream_generator, sources, estimated_input_tokens).
    """
    llm = get_llm_provider(llm_provider, llm_model)

    # Query expansion
    if expand_queries:
        queries = await expand_query(query, llm)
    else:
        queries = [query]

    # Multi-query retrieval
    all_hits: list[dict] = []
    for q in queries:
        hits = await hybrid_search(
            project_id, q, k=max_context_chunks * 2,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
        all_hits.extend(hits)

    # Deduplicate by content fingerprint
    seen: set[str] = set()
    unique_hits = []
    for hit in all_hits:
        key = hit["content"][:100]
        if key not in seen:
            seen.add(key)
            unique_hits.append(hit)

    # Re-rank
    reranked = await rerank(query, unique_hits, top_k=max_context_chunks)

    # Build context
    context, sources = build_context(reranked, max_chars=8000)

    # Build messages
    base_system = system_prompt or "You are a helpful assistant. Answer questions based on the provided context."

    messages: list[dict] = [{"role": "system", "content": base_system}]

    if context:
        messages.append({
            "role": "user",
            "content": f"Use the following context to answer the question.\n\nContext:\n{context}\n\nQuestion: {query}",
        })
    else:
        messages.append({"role": "user", "content": query})

    # Include conversation history (last 10 turns)
    history = conversation_history[-20:]
    if history and messages[-1]["role"] == "user":
        # Reorder: history before current question
        current_user_msg = messages.pop()
        for h in history:
            messages.append(h)
        messages.append(current_user_msg)

    # Estimate tokens (rough: 4 chars per token)
    estimated_tokens = sum(len(m["content"]) // 4 for m in messages)

    async def _stream() -> AsyncGenerator[str, None]:
        async for chunk in llm.generate_stream(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    return _stream(), sources, estimated_tokens


async def simple_chat_stream(
    query: str,
    conversation_history: list[dict],
    system_prompt: Optional[str],
    llm_provider: str,
    llm_model: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """Chat without RAG (no documents)."""
    llm = get_llm_provider(llm_provider, llm_model)
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for h in conversation_history[-20:]:
        messages.append(h)

    messages.append({"role": "user", "content": query})

    async def _stream() -> AsyncGenerator[str, None]:
        async for chunk in llm.generate_stream(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    return _stream()
