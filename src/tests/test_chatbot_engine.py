"""pytest tests for chatbot engine: LLM providers, RAG pipeline, and streaming."""

import asyncio
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.chatbot_engine import (
    AnthropicProvider,
    GeminiProvider,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    build_context,
    expand_query,
    get_llm_provider,
    rag_answer_stream,
    simple_chat_stream,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def collect_stream(gen: AsyncGenerator[str, None]) -> str:
    chunks: list[str] = []
    async for chunk in gen:
        chunks.append(chunk)
    return "".join(chunks)


def make_provider_mock(response_chunks: list[str]) -> MagicMock:
    async def _stream(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
        for chunk in response_chunks:
            yield chunk

    mock = MagicMock(spec=LLMProvider)
    mock.generate_stream = _stream
    mock.generate = AsyncMock(return_value="".join(response_chunks))
    return mock


def make_hit(content: str, score: float = 0.8, doc_id: str = "doc1", filename: str = "test.txt") -> dict[str, Any]:
    return {
        "content": content,
        "metadata": {
            "document_id": doc_id,
            "filename": filename,
            "chunk_index": 0,
        },
        "score": score,
        "search_type": "dense",
    }


# ─── LLMProvider base ────────────────────────────────────────────────────────

class TestLLMProviderBase:
    def test_generate_stream_raises(self) -> None:
        provider = LLMProvider()
        messages = [{"role": "user", "content": "hello"}]

        async def run() -> None:
            gen = provider.generate_stream(messages)
            async for _ in gen:
                pass

        with pytest.raises((NotImplementedError, TypeError)):
            asyncio.get_event_loop().run_until_complete(run())

    @pytest.mark.asyncio
    async def test_generate_collects_stream(self) -> None:
        async def mock_stream(messages: list[dict], **kwargs: Any) -> AsyncGenerator[str, None]:
            for chunk in ["Hello", " ", "world"]:
                yield chunk

        provider = LLMProvider()
        provider.generate_stream = mock_stream  # type: ignore[method-assign]
        result = await provider.generate([{"role": "user", "content": "hi"}])
        assert result == "Hello world"


# ─── AnthropicProvider ────────────────────────────────────────────────────────

class TestAnthropicProvider:
    def test_init_default_model(self) -> None:
        provider = AnthropicProvider(api_key="test-key")
        assert provider.model == "claude-sonnet-4-6"
        assert provider.api_key == "test-key"

    def test_init_custom_model(self) -> None:
        provider = AnthropicProvider(api_key="test-key", model="claude-opus-4-7")
        assert provider.model == "claude-opus-4-7"

    @pytest.mark.asyncio
    async def test_generate_stream_mocked(self) -> None:
        provider = AnthropicProvider(api_key="test-key")

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        async def fake_text_stream() -> AsyncGenerator[str, None]:
            for word in ["Hello", " there", "!"]:
                yield word

        mock_stream_ctx.text_stream = fake_text_stream()

        mock_messages = MagicMock()
        mock_messages.stream = MagicMock(return_value=mock_stream_ctx)

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        with patch("src.chatbot_engine.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await collect_stream(
                provider.generate_stream([{"role": "user", "content": "hi"}])
            )

        assert result == "Hello there!"


# ─── OpenAIProvider ───────────────────────────────────────────────────────────

class TestOpenAIProvider:
    def test_init(self) -> None:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert provider.model == "gpt-4o"
        assert provider.api_key == "sk-test"

    @pytest.mark.asyncio
    async def test_generate_stream_mocked(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "Hello"

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = " world"

        mock_chunk3 = MagicMock()
        mock_chunk3.choices = [MagicMock()]
        mock_chunk3.choices[0].delta.content = None

        async def fake_aiter(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
            for chunk in [mock_chunk1, mock_chunk2, mock_chunk3]:
                yield chunk

        mock_completion = AsyncMock()
        mock_completion.__aiter__ = fake_aiter

        mock_chat = AsyncMock()
        mock_chat.completions.create = AsyncMock(return_value=mock_completion)

        mock_client = MagicMock()
        mock_client.chat = mock_chat

        with patch("src.chatbot_engine.AsyncOpenAI", return_value=mock_client):
            result = await collect_stream(
                provider.generate_stream([{"role": "user", "content": "hi"}])
            )

        assert "Hello" in result
        assert "world" in result


# ─── OllamaProvider ───────────────────────────────────────────────────────────

class TestOllamaProvider:
    def test_init(self) -> None:
        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
        assert provider.model == "llama3.2"
        assert "11434" in provider.base_url


# ─── get_llm_provider ─────────────────────────────────────────────────────────

class TestGetLlmProvider:
    def setup_method(self) -> None:
        from src.chatbot_engine import _llm_providers
        _llm_providers.clear()

    def test_anthropic_provider(self) -> None:
        provider = get_llm_provider("anthropic", "claude-sonnet-4-6")
        assert isinstance(provider, AnthropicProvider)

    def test_openai_provider(self) -> None:
        provider = get_llm_provider("openai", "gpt-4o")
        assert isinstance(provider, OpenAIProvider)

    def test_google_provider(self) -> None:
        provider = get_llm_provider("google", "gemini-1.5-flash")
        assert isinstance(provider, GeminiProvider)

    def test_ollama_provider(self) -> None:
        provider = get_llm_provider("ollama", "llama3.2")
        assert isinstance(provider, OllamaProvider)

    def test_unknown_falls_back_to_anthropic(self) -> None:
        provider = get_llm_provider("unknown_provider", "some-model")
        assert isinstance(provider, AnthropicProvider)

    def test_caches_instance(self) -> None:
        p1 = get_llm_provider("anthropic", "claude-sonnet-4-6")
        p2 = get_llm_provider("anthropic", "claude-sonnet-4-6")
        assert p1 is p2

    def test_different_models_different_instances(self) -> None:
        p1 = get_llm_provider("anthropic", "claude-sonnet-4-6")
        p2 = get_llm_provider("anthropic", "claude-opus-4-7")
        assert p1 is not p2


# ─── build_context ────────────────────────────────────────────────────────────

class TestBuildContext:
    def test_empty_hits(self) -> None:
        context, sources = build_context([])
        assert context == ""
        assert sources == []

    def test_single_hit(self) -> None:
        hits = [make_hit("Important information about the product.")]
        context, sources = build_context(hits)
        assert "Important information" in context
        assert len(sources) == 1
        assert sources[0]["index"] == 1
        assert sources[0]["document_name"] == "test.txt"

    def test_multiple_hits(self) -> None:
        hits = [make_hit(f"Content {i}.", score=float(i) * 0.1, doc_id=f"doc{i}") for i in range(3)]
        context, sources = build_context(hits)
        assert len(sources) == 3
        for i, src in enumerate(sources):
            assert src["index"] == i + 1

    def test_respects_max_chars(self) -> None:
        long_content = "A" * 2000
        hits = [make_hit(long_content) for _ in range(5)]
        context, sources = build_context(hits, max_chars=3000)
        assert len(context) <= 5000

    def test_source_content_truncated(self) -> None:
        long_text = "word " * 100
        hits = [make_hit(long_text)]
        _, sources = build_context(hits)
        assert len(sources[0]["content"]) <= 203

    def test_uses_source_url_when_no_filename(self) -> None:
        hit: dict[str, Any] = {
            "content": "Web page content here.",
            "metadata": {"document_id": "d1", "source_url": "https://example.com", "chunk_index": 0},
            "score": 0.9,
        }
        _, sources = build_context([hit])
        assert sources[0]["document_name"] == "https://example.com"

    def test_score_rounded(self) -> None:
        hits = [make_hit("content", score=0.123456789)]
        _, sources = build_context(hits)
        assert sources[0]["score"] == pytest.approx(0.123, abs=0.001)

    def test_context_separator(self) -> None:
        hits = [make_hit("Content A."), make_hit("Content B.")]
        context, _ = build_context(hits)
        assert "---" in context


# ─── expand_query ─────────────────────────────────────────────────────────────

class TestExpandQuery:
    @pytest.mark.asyncio
    async def test_returns_original_plus_variants(self) -> None:
        mock_provider = make_provider_mock(["Variant one query\nVariant two query"])
        result = await expand_query("What is machine learning?", mock_provider)
        assert result[0] == "What is machine learning?"
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_returns_only_original_on_error(self) -> None:
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate = AsyncMock(side_effect=Exception("API error"))

        result = await expand_query("test query", mock_provider)
        assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_max_two_alternatives(self) -> None:
        mock_provider = make_provider_mock(["Alt1\nAlt2\nAlt3\nAlt4"])
        result = await expand_query("original", mock_provider)
        assert len(result) <= 3


# ─── rag_answer_stream ────────────────────────────────────────────────────────

class TestRagAnswerStream:
    @pytest.mark.asyncio
    async def test_returns_stream_sources_tokens(self) -> None:
        hits = [make_hit("Relevant document content about the answer.", score=0.9)]

        with patch("src.chatbot_engine.hybrid_search", new_callable=AsyncMock, return_value=hits):
            with patch("src.chatbot_engine.rerank", new_callable=AsyncMock, return_value=hits):
                with patch("src.chatbot_engine.expand_query", new_callable=AsyncMock, return_value=["test"]):
                    mock_provider = make_provider_mock(["The answer is 42."])
                    with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
                        stream, sources, estimated_tokens = await rag_answer_stream(
                            project_id="proj-1",
                            query="What is the answer?",
                            conversation_history=[],
                            system_prompt="You are helpful.",
                            llm_provider="anthropic",
                            llm_model="claude-sonnet-4-6",
                            embedding_provider="sentence_transformers",
                            embedding_model="all-MiniLM-L6-v2",
                        )

        result = await collect_stream(stream)
        assert "42" in result
        assert isinstance(sources, list)
        assert isinstance(estimated_tokens, int)
        assert estimated_tokens > 0

    @pytest.mark.asyncio
    async def test_sources_from_hits(self) -> None:
        hits = [make_hit("Answer content.", doc_id="doc-abc", filename="manual.pdf")]

        with patch("src.chatbot_engine.hybrid_search", new_callable=AsyncMock, return_value=hits):
            with patch("src.chatbot_engine.rerank", new_callable=AsyncMock, return_value=hits):
                with patch("src.chatbot_engine.expand_query", new_callable=AsyncMock, return_value=["q"]):
                    mock_provider = make_provider_mock(["response"])
                    with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
                        _, sources, _ = await rag_answer_stream(
                            project_id="proj-1",
                            query="question",
                            conversation_history=[],
                            system_prompt=None,
                            llm_provider="anthropic",
                            llm_model="claude-sonnet-4-6",
                            embedding_provider="sentence_transformers",
                            embedding_model="all-MiniLM-L6-v2",
                        )

        assert len(sources) >= 1
        assert sources[0]["document_name"] == "manual.pdf"

    @pytest.mark.asyncio
    async def test_deduplicates_hits(self) -> None:
        duplicate_hit = make_hit("Same content appears twice", score=0.9)
        hits = [duplicate_hit, duplicate_hit, make_hit("Different content", score=0.7)]

        with patch("src.chatbot_engine.hybrid_search", new_callable=AsyncMock, return_value=hits):
            with patch("src.chatbot_engine.rerank", new_callable=AsyncMock, return_value=[duplicate_hit]):
                with patch("src.chatbot_engine.expand_query", new_callable=AsyncMock, return_value=["q"]):
                    mock_provider = make_provider_mock(["ok"])
                    with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
                        _, sources, _ = await rag_answer_stream(
                            project_id="proj",
                            query="q",
                            conversation_history=[],
                            system_prompt=None,
                            llm_provider="anthropic",
                            llm_model="claude-sonnet-4-6",
                            embedding_provider="sentence_transformers",
                            embedding_model="all-MiniLM-L6-v2",
                        )
        assert len(sources) <= 2

    @pytest.mark.asyncio
    async def test_no_expand_when_disabled(self) -> None:
        hits = [make_hit("content")]

        with patch("src.chatbot_engine.hybrid_search", new_callable=AsyncMock, return_value=hits) as mock_search:
            with patch("src.chatbot_engine.rerank", new_callable=AsyncMock, return_value=hits):
                with patch("src.chatbot_engine.expand_query", new_callable=AsyncMock) as mock_expand:
                    mock_provider = make_provider_mock(["ok"])
                    with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
                        await rag_answer_stream(
                            project_id="proj",
                            query="q",
                            conversation_history=[],
                            system_prompt=None,
                            llm_provider="anthropic",
                            llm_model="claude-sonnet-4-6",
                            embedding_provider="sentence_transformers",
                            embedding_model="all-MiniLM-L6-v2",
                            expand_queries=False,
                        )

        mock_expand.assert_not_called()
        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_includes_conversation_history(self) -> None:
        hits: list[dict[str, Any]] = []
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        with patch("src.chatbot_engine.hybrid_search", new_callable=AsyncMock, return_value=hits):
            with patch("src.chatbot_engine.rerank", new_callable=AsyncMock, return_value=hits):
                with patch("src.chatbot_engine.expand_query", new_callable=AsyncMock, return_value=["q"]):
                    mock_provider = make_provider_mock(["response"])
                    mock_provider.generate_stream = MagicMock()

                    captured_messages: list[list[dict[str, Any]]] = []

                    async def capture_stream(msgs: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[str, None]:
                        captured_messages.append(msgs)
                        yield "response"

                    mock_provider.generate_stream = capture_stream

                    with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
                        stream, _, _ = await rag_answer_stream(
                            project_id="proj",
                            query="new question",
                            conversation_history=history,
                            system_prompt=None,
                            llm_provider="anthropic",
                            llm_model="claude-sonnet-4-6",
                            embedding_provider="sentence_transformers",
                            embedding_model="all-MiniLM-L6-v2",
                        )
                        await collect_stream(stream)

        all_messages = captured_messages[0] if captured_messages else []
        all_content = " ".join(m["content"] for m in all_messages)
        assert "Previous question" in all_content or "Previous answer" in all_content


# ─── simple_chat_stream ───────────────────────────────────────────────────────

class TestSimpleChatStream:
    @pytest.mark.asyncio
    async def test_basic_stream(self) -> None:
        mock_provider = make_provider_mock(["Hello", " from", " chat"])
        with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
            stream = await simple_chat_stream(
                query="Hello",
                conversation_history=[],
                system_prompt=None,
                llm_provider="anthropic",
                llm_model="claude-sonnet-4-6",
            )
        result = await collect_stream(stream)
        assert "Hello" in result
        assert "chat" in result

    @pytest.mark.asyncio
    async def test_includes_system_prompt(self) -> None:
        captured: list[list[dict[str, Any]]] = []

        async def capture_stream(messages: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[str, None]:
            captured.append(messages)
            yield "ok"

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate_stream = capture_stream

        with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
            stream = await simple_chat_stream(
                query="question",
                conversation_history=[],
                system_prompt="You are a pirate.",
                llm_provider="anthropic",
                llm_model="claude-sonnet-4-6",
            )
        await collect_stream(stream)

        messages = captured[0]
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert any("pirate" in m["content"] for m in system_msgs)

    @pytest.mark.asyncio
    async def test_includes_conversation_history(self) -> None:
        captured: list[list[dict[str, Any]]] = []

        async def capture_stream(messages: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[str, None]:
            captured.append(messages)
            yield "ok"

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate_stream = capture_stream
        history = [
            {"role": "user", "content": "prior user message"},
            {"role": "assistant", "content": "prior assistant message"},
        ]

        with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
            stream = await simple_chat_stream(
                query="new question",
                conversation_history=history,
                system_prompt=None,
                llm_provider="anthropic",
                llm_model="claude-sonnet-4-6",
            )
        await collect_stream(stream)

        messages = captured[0]
        all_content = " ".join(m["content"] for m in messages)
        assert "prior user message" in all_content

    @pytest.mark.asyncio
    async def test_last_message_is_user_query(self) -> None:
        captured: list[list[dict[str, Any]]] = []

        async def capture_stream(messages: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[str, None]:
            captured.append(messages)
            yield "ok"

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate_stream = capture_stream

        with patch("src.chatbot_engine.get_llm_provider", return_value=mock_provider):
            stream = await simple_chat_stream(
                query="the final question",
                conversation_history=[{"role": "user", "content": "old"}, {"role": "assistant", "content": "old ans"}],
                system_prompt=None,
                llm_provider="anthropic",
                llm_model="claude-sonnet-4-6",
            )
        await collect_stream(stream)

        messages = captured[0]
        last_msg = messages[-1]
        assert last_msg["role"] == "user"
        assert last_msg["content"] == "the final question"
