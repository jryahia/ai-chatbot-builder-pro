"""ChromaDB + BM25 hybrid search with re-ranking."""

import asyncio
import uuid
from typing import Any, Optional

import numpy as np
import structlog
from rank_bm25 import BM25Okapi

from src.config import settings

logger = structlog.get_logger(__name__)


# ─── Embedding Providers ──────────────────────────────────────────────────────

class EmbeddingProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, lambda: model.encode(texts, show_progress_bar=False))
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        model = self._load()
        return model.get_sentence_embedding_dimension()


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "text-embedding-3-small", api_key: Optional[str] = None) -> None:
        self.model_name = model_name
        self.api_key = api_key or settings.openai_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key, base_url=settings.openai_base_url)
        response = await client.embeddings.create(model=self.model_name, input=texts)
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return 1536 if "small" in self.model_name else 3072


_embedding_providers: dict[str, EmbeddingProvider] = {}


def get_embedding_provider(provider: str, model: str) -> EmbeddingProvider:
    key = f"{provider}:{model}"
    if key not in _embedding_providers:
        if provider == "sentence_transformers":
            _embedding_providers[key] = SentenceTransformerProvider(model)
        elif provider == "openai":
            _embedding_providers[key] = OpenAIEmbeddingProvider(model)
        else:
            _embedding_providers[key] = SentenceTransformerProvider("all-MiniLM-L6-v2")
    return _embedding_providers[key]


# ─── ChromaDB Store ───────────────────────────────────────────────────────────

_chroma_client = None


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _chroma_client


def _collection_name(project_id: str) -> str:
    return f"{settings.chroma_collection_prefix}{project_id.replace('-', '_')}"


async def upsert_chunks(
    project_id: str,
    chunks: list[dict],
    embedding_provider: str = "sentence_transformers",
    embedding_model: str = "all-MiniLM-L6-v2",
) -> list[str]:
    """Embed and upsert chunks into ChromaDB. Returns chroma IDs."""
    if not chunks:
        return []

    provider = get_embedding_provider(embedding_provider, embedding_model)
    texts = [c["content"] for c in chunks]

    loop = asyncio.get_event_loop()
    client = await loop.run_in_executor(None, _get_chroma_client)

    collection_name = _collection_name(project_id)
    collection = await loop.run_in_executor(
        None,
        lambda: client.get_or_create_collection(collection_name, metadata={"hnsw:space": "cosine"}),
    )

    # Batch embed
    batch_size = 64
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        embeddings = await provider.embed(batch)
        all_embeddings.extend(embeddings)

    chroma_ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [
        {
            "document_id": c.get("document_id", ""),
            "project_id": project_id,
            "chunk_index": int(c.get("chunk_index", 0)),
            "token_count": int(c.get("token_count", 0)),
            **(c.get("metadata") or {}),
        }
        for c in chunks
    ]
    # Chroma metadata values must be str/int/float/bool
    clean_metadatas = []
    for m in metadatas:
        clean = {}
        for k, v in m.items():
            if isinstance(v, (str, int, float, bool)):
                clean[k] = v
            elif v is None:
                clean[k] = ""
            else:
                clean[k] = str(v)
        clean_metadatas.append(clean)

    await loop.run_in_executor(
        None,
        lambda: collection.upsert(
            ids=chroma_ids,
            documents=texts,
            embeddings=all_embeddings,
            metadatas=clean_metadatas,
        ),
    )

    return chroma_ids


async def delete_chunks_by_document(project_id: str, document_id: str) -> None:
    loop = asyncio.get_event_loop()
    client = await loop.run_in_executor(None, _get_chroma_client)
    collection_name = _collection_name(project_id)
    try:
        collection = await loop.run_in_executor(
            None, lambda: client.get_collection(collection_name)
        )
        await loop.run_in_executor(
            None,
            lambda: collection.delete(where={"document_id": document_id}),
        )
    except Exception as e:
        logger.warning("delete_chunks_failed", error=str(e))


async def dense_search(
    project_id: str,
    query: str,
    k: int = 10,
    embedding_provider: str = "sentence_transformers",
    embedding_model: str = "all-MiniLM-L6-v2",
) -> list[dict]:
    """Dense vector search using ChromaDB."""
    provider = get_embedding_provider(embedding_provider, embedding_model)
    query_embedding = (await provider.embed([query]))[0]

    loop = asyncio.get_event_loop()
    client = await loop.run_in_executor(None, _get_chroma_client)
    collection_name = _collection_name(project_id)

    try:
        collection = await loop.run_in_executor(
            None, lambda: client.get_collection(collection_name)
        )
        results = await loop.run_in_executor(
            None,
            lambda: collection.query(
                query_embeddings=[query_embedding],
                n_results=min(k, collection.count()),
                include=["documents", "metadatas", "distances"],
            ),
        )
    except Exception as e:
        logger.warning("dense_search_failed", error=str(e))
        return []

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "content": doc,
            "metadata": meta,
            "score": float(1 - dist),
            "search_type": "dense",
        })
    return hits


async def get_collection_stats(project_id: str) -> dict:
    loop = asyncio.get_event_loop()
    client = await loop.run_in_executor(None, _get_chroma_client)
    collection_name = _collection_name(project_id)
    try:
        collection = await loop.run_in_executor(
            None, lambda: client.get_collection(collection_name)
        )
        count = await loop.run_in_executor(None, collection.count)
        return {"total_chunks": count, "collection_name": collection_name}
    except Exception:
        return {"total_chunks": 0, "collection_name": collection_name}


# ─── BM25 Sparse Search ───────────────────────────────────────────────────────

class BM25Index:
    def __init__(self) -> None:
        self._corpus: list[str] = []
        self._metadatas: list[dict] = []
        self._bm25: Optional[BM25Okapi] = None

    def _tokenize(self, text: str) -> list[str]:
        return text.lower().split()

    def build(self, texts: list[str], metadatas: list[dict]) -> None:
        self._corpus = texts
        self._metadatas = metadatas
        tokenized = [self._tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def search(self, query: str, k: int = 10) -> list[dict]:
        if not self._bm25 or not self._corpus:
            return []
        scores = self._bm25.get_scores(self._tokenize(query))
        top_idx = np.argsort(scores)[::-1][:k]
        results = []
        for idx in top_idx:
            if scores[idx] > 0:
                results.append({
                    "content": self._corpus[idx],
                    "metadata": self._metadatas[idx],
                    "score": float(scores[idx]),
                    "search_type": "sparse",
                })
        return results


_bm25_indexes: dict[str, BM25Index] = {}


async def build_bm25_index(project_id: str, texts: list[str], metadatas: list[dict]) -> None:
    idx = BM25Index()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: idx.build(texts, metadatas))
    _bm25_indexes[project_id] = idx


async def bm25_search(project_id: str, query: str, k: int = 10) -> list[dict]:
    idx = _bm25_indexes.get(project_id)
    if not idx:
        return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: idx.search(query, k))


# ─── Hybrid Search ────────────────────────────────────────────────────────────

def _normalize_scores(hits: list[dict]) -> list[dict]:
    if not hits:
        return hits
    scores = [h["score"] for h in hits]
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        for h in hits:
            h["score"] = 1.0
        return hits
    for h in hits:
        h["score"] = (h["score"] - min_s) / (max_s - min_s)
    return hits


async def hybrid_search(
    project_id: str,
    query: str,
    k: int = 5,
    embedding_provider: str = "sentence_transformers",
    embedding_model: str = "all-MiniLM-L6-v2",
    alpha: float = 0.7,
) -> list[dict]:
    """
    Hybrid dense + sparse search.
    alpha=1.0 → pure dense, alpha=0.0 → pure sparse.
    """
    dense_k = k * 2
    sparse_k = k * 2

    dense_hits, sparse_hits = await asyncio.gather(
        dense_search(project_id, query, dense_k, embedding_provider, embedding_model),
        bm25_search(project_id, query, sparse_k),
    )

    dense_hits = _normalize_scores(dense_hits)
    sparse_hits = _normalize_scores(sparse_hits)

    # Merge by content fingerprint
    combined: dict[str, dict] = {}
    for hit in dense_hits:
        key = hit["content"][:100]
        combined[key] = {**hit, "dense_score": hit["score"], "sparse_score": 0.0}

    for hit in sparse_hits:
        key = hit["content"][:100]
        if key in combined:
            combined[key]["sparse_score"] = hit["score"]
        else:
            combined[key] = {**hit, "dense_score": 0.0, "sparse_score": hit["score"]}

    for item in combined.values():
        item["score"] = alpha * item["dense_score"] + (1 - alpha) * item["sparse_score"]

    ranked = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:k]


# ─── Re-ranking ───────────────────────────────────────────────────────────────

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logger.warning("reranker_load_failed", error=str(e))
            _reranker = False
    return _reranker if _reranker is not False else None


async def rerank(query: str, hits: list[dict], top_k: int = 5) -> list[dict]:
    """Re-rank results using a cross-encoder."""
    if not hits:
        return hits

    reranker = _get_reranker()
    if not reranker:
        return hits[:top_k]

    pairs = [(query, h["content"]) for h in hits]
    loop = asyncio.get_event_loop()
    scores = await loop.run_in_executor(None, lambda: reranker.predict(pairs))

    for hit, score in zip(hits, scores):
        hit["rerank_score"] = float(score)

    reranked = sorted(hits, key=lambda x: x.get("rerank_score", x["score"]), reverse=True)
    return reranked[:top_k]
