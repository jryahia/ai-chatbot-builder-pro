"""pytest tests for vector store: embeddings, ChromaDB ops, BM25, hybrid search, re-ranking."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.vector_store import (
    BM25Index,
    EmbeddingProvider,
    SentenceTransformerProvider,
    _normalize_scores,
    bm25_search,
    build_bm25_index,
    dense_search,
    get_collection_stats,
    get_embedding_provider,
    hybrid_search,
    rerank,
    upsert_chunks,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_hit(content: str, score: float, search_type: str = "dense") -> dict[str, Any]:
    return {
        "content": content,
        "metadata": {"document_id": "doc1", "chunk_index": 0},
        "score": score,
        "search_type": search_type,
    }


SAMPLE_TEXTS = [
    "Machine learning is a subset of artificial intelligence.",
    "Deep learning uses neural networks with many layers.",
    "Natural language processing enables computers to understand text.",
    "Computer vision allows machines to interpret images.",
    "Reinforcement learning trains agents through rewards and penalties.",
]

SAMPLE_METADATAS = [
    {"document_id": f"doc_{i}", "chunk_index": i} for i in range(len(SAMPLE_TEXTS))
]


# ─── _normalize_scores ────────────────────────────────────────────────────────

class TestNormalizeScores:
    def test_empty_list(self) -> None:
        result = _normalize_scores([])
        assert result == []

    def test_single_hit(self) -> None:
        hits = [make_hit("text", 0.8)]
        result = _normalize_scores(hits)
        assert result[0]["score"] == 1.0

    def test_all_same_score(self) -> None:
        hits = [make_hit(f"text {i}", 0.5) for i in range(3)]
        result = _normalize_scores(hits)
        for h in result:
            assert h["score"] == 1.0

    def test_normalizes_to_zero_one(self) -> None:
        hits = [make_hit(f"text {i}", float(i)) for i in range(5)]
        result = _normalize_scores(hits)
        scores = [h["score"] for h in result]
        assert min(scores) == pytest.approx(0.0)
        assert max(scores) == pytest.approx(1.0)

    def test_preserves_order(self) -> None:
        hits = [make_hit(f"text {i}", float(i * 0.1)) for i in range(4)]
        result = _normalize_scores(hits)
        assert result[0]["score"] < result[-1]["score"]


# ─── BM25Index ────────────────────────────────────────────────────────────────

class TestBM25Index:
    def test_build_and_search(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_TEXTS, SAMPLE_METADATAS)
        results = idx.search("machine learning neural", k=3)
        assert isinstance(results, list)
        assert len(results) <= 3
        for r in results:
            assert "content" in r
            assert "score" in r
            assert r["score"] > 0

    def test_search_before_build_returns_empty(self) -> None:
        idx = BM25Index()
        results = idx.search("query", k=5)
        assert results == []

    def test_relevant_result_ranked_first(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_TEXTS, SAMPLE_METADATAS)
        results = idx.search("machine learning artificial intelligence", k=5)
        contents = [r["content"] for r in results]
        assert any("machine learning" in c.lower() or "artificial intelligence" in c.lower() for c in contents)

    def test_no_match_returns_empty(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_TEXTS, SAMPLE_METADATAS)
        results = idx.search("zzzzz xxxxxxxxxxx qqqqq", k=5)
        assert results == []

    def test_top_k_limit(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_TEXTS, SAMPLE_METADATAS)
        results = idx.search("learning", k=2)
        assert len(results) <= 2

    def test_search_type_is_sparse(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_TEXTS, SAMPLE_METADATAS)
        results = idx.search("deep learning", k=3)
        for r in results:
            assert r["search_type"] == "sparse"

    def test_metadata_preserved(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_TEXTS, SAMPLE_METADATAS)
        results = idx.search("computer vision", k=2)
        for r in results:
            assert "document_id" in r["metadata"]


# ─── build_bm25_index / bm25_search ──────────────────────────────────────────

class TestBm25AsyncFunctions:
    @pytest.mark.asyncio
    async def test_build_then_search(self) -> None:
        project_id = "test-project-bm25"
        await build_bm25_index(project_id, SAMPLE_TEXTS, SAMPLE_METADATAS)
        results = await bm25_search(project_id, "neural networks deep learning", k=3)
        assert isinstance(results, list)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_missing_index_returns_empty(self) -> None:
        results = await bm25_search("nonexistent-project-xyz", "any query", k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_rebuild_index(self) -> None:
        project_id = "test-project-rebuild"
        await build_bm25_index(project_id, SAMPLE_TEXTS, SAMPLE_METADATAS)
        new_texts = ["Completely different content about cooking recipes."]
        new_meta = [{"document_id": "new_doc", "chunk_index": 0}]
        await build_bm25_index(project_id, new_texts, new_meta)
        results = await bm25_search(project_id, "cooking recipes", k=5)
        assert any("cooking" in r["content"].lower() for r in results)


# ─── EmbeddingProvider ────────────────────────────────────────────────────────

class TestEmbeddingProviderBase:
    def test_embed_raises_not_implemented(self) -> None:
        provider = EmbeddingProvider()
        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(provider.embed(["test"]))

    def test_dimension_raises_not_implemented(self) -> None:
        provider = EmbeddingProvider()
        with pytest.raises(NotImplementedError):
            _ = provider.dimension


class TestSentenceTransformerProvider:
    def test_init(self) -> None:
        provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
        assert provider.model_name == "all-MiniLM-L6-v2"

    @pytest.mark.asyncio
    async def test_embed_with_mock_model(self) -> None:
        provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        mock_model.get_sentence_embedding_dimension.return_value = 3
        provider._model = mock_model

        texts = ["hello world", "foo bar"]
        result = await provider.embed(texts)
        assert len(result) == 2
        assert len(result[0]) == 3
        mock_model.encode.assert_called_once()

    def test_dimension_with_mock_model(self) -> None:
        provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        provider._model = mock_model
        assert provider.dimension == 384


# ─── get_embedding_provider ───────────────────────────────────────────────────

class TestGetEmbeddingProvider:
    def test_sentence_transformers(self) -> None:
        from src.vector_store import _embedding_providers
        key = "sentence_transformers:all-MiniLM-L6-v2"
        _embedding_providers.pop(key, None)
        provider = get_embedding_provider("sentence_transformers", "all-MiniLM-L6-v2")
        assert isinstance(provider, SentenceTransformerProvider)

    def test_unknown_provider_falls_back_to_sentence_transformer(self) -> None:
        from src.vector_store import _embedding_providers
        key = "unknown:some-model"
        _embedding_providers.pop(key, None)
        provider = get_embedding_provider("unknown", "some-model")
        assert isinstance(provider, SentenceTransformerProvider)

    def test_same_key_returns_cached(self) -> None:
        p1 = get_embedding_provider("sentence_transformers", "all-MiniLM-L6-v2")
        p2 = get_embedding_provider("sentence_transformers", "all-MiniLM-L6-v2")
        assert p1 is p2


# ─── upsert_chunks ────────────────────────────────────────────────────────────

class TestUpsertChunks:
    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self) -> None:
        result = await upsert_chunks("proj-1", [], "sentence_transformers", "all-MiniLM-L6-v2")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_chroma_ids(self) -> None:
        chunks = [
            {"content": "text one", "chunk_index": 0, "token_count": 3, "document_id": "d1", "metadata": {}},
            {"content": "text two", "chunk_index": 1, "token_count": 3, "document_id": "d1", "metadata": {}},
        ]
        mock_provider = AsyncMock(spec=EmbeddingProvider)
        mock_provider.embed = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])

        mock_collection = MagicMock()
        mock_collection.upsert = MagicMock()

        mock_client = MagicMock()
        mock_client.get_or_create_collection = MagicMock(return_value=mock_collection)

        with patch("src.vector_store.get_embedding_provider", return_value=mock_provider):
            with patch("src.vector_store._get_chroma_client", return_value=mock_client):
                result = await upsert_chunks("proj-1", chunks)
        assert len(result) == 2
        for chroma_id in result:
            assert isinstance(chroma_id, str)
            assert len(chroma_id) > 0


# ─── dense_search ─────────────────────────────────────────────────────────────

class TestDenseSearch:
    @pytest.mark.asyncio
    async def test_returns_hits(self) -> None:
        mock_provider = AsyncMock(spec=EmbeddingProvider)
        mock_provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        mock_results: dict[str, Any] = {
            "documents": [["content A", "content B"]],
            "metadatas": [[{"document_id": "d1", "chunk_index": 0}, {"document_id": "d2", "chunk_index": 1}]],
            "distances": [[0.1, 0.3]],
        }
        mock_collection = MagicMock()
        mock_collection.query = MagicMock(return_value=mock_results)
        mock_collection.count = MagicMock(return_value=2)

        mock_client = MagicMock()
        mock_client.get_collection = MagicMock(return_value=mock_collection)

        with patch("src.vector_store.get_embedding_provider", return_value=mock_provider):
            with patch("src.vector_store._get_chroma_client", return_value=mock_client):
                hits = await dense_search("proj-1", "test query", k=2)

        assert len(hits) == 2
        assert hits[0]["content"] == "content A"
        assert hits[0]["score"] == pytest.approx(0.9)
        assert hits[0]["search_type"] == "dense"

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self) -> None:
        mock_provider = AsyncMock(spec=EmbeddingProvider)
        mock_provider.embed = AsyncMock(return_value=[[0.1, 0.2]])

        mock_client = MagicMock()
        mock_client.get_collection = MagicMock(side_effect=Exception("collection not found"))

        with patch("src.vector_store.get_embedding_provider", return_value=mock_provider):
            with patch("src.vector_store._get_chroma_client", return_value=mock_client):
                hits = await dense_search("proj-missing", "query")

        assert hits == []


# ─── get_collection_stats ─────────────────────────────────────────────────────

class TestGetCollectionStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self) -> None:
        mock_collection = MagicMock()
        mock_collection.count = MagicMock(return_value=42)

        mock_client = MagicMock()
        mock_client.get_collection = MagicMock(return_value=mock_collection)

        with patch("src.vector_store._get_chroma_client", return_value=mock_client):
            stats = await get_collection_stats("proj-1")

        assert stats["total_chunks"] == 42
        assert "collection_name" in stats

    @pytest.mark.asyncio
    async def test_returns_zero_on_missing_collection(self) -> None:
        mock_client = MagicMock()
        mock_client.get_collection = MagicMock(side_effect=Exception("not found"))

        with patch("src.vector_store._get_chroma_client", return_value=mock_client):
            stats = await get_collection_stats("proj-missing")

        assert stats["total_chunks"] == 0


# ─── hybrid_search ────────────────────────────────────────────────────────────

class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_merges_dense_and_sparse(self) -> None:
        dense_hits = [
            make_hit("shared content first", 0.9, "dense"),
            make_hit("dense only content", 0.7, "dense"),
        ]
        sparse_hits = [
            make_hit("shared content first", 0.8, "sparse"),
            make_hit("sparse only content", 0.6, "sparse"),
        ]

        with patch("src.vector_store.dense_search", new_callable=AsyncMock, return_value=dense_hits):
            with patch("src.vector_store.bm25_search", new_callable=AsyncMock, return_value=sparse_hits):
                results = await hybrid_search("proj-1", "test query", k=4)

        assert isinstance(results, list)
        assert len(results) <= 4
        contents = [r["content"] for r in results]
        assert "shared content first" in contents

    @pytest.mark.asyncio
    async def test_alpha_pure_dense(self) -> None:
        dense_hits = [make_hit(f"dense {i}", float(i) * 0.1, "dense") for i in range(4)]
        sparse_hits: list[dict[str, Any]] = []

        with patch("src.vector_store.dense_search", new_callable=AsyncMock, return_value=dense_hits):
            with patch("src.vector_store.bm25_search", new_callable=AsyncMock, return_value=sparse_hits):
                results = await hybrid_search("proj-1", "query", k=3, alpha=1.0)

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_returns_k_results(self) -> None:
        dense_hits = [make_hit(f"content {i}", float(i) * 0.1) for i in range(10)]
        sparse_hits = [make_hit(f"sparse {i}", float(i) * 0.05) for i in range(10)]

        with patch("src.vector_store.dense_search", new_callable=AsyncMock, return_value=dense_hits):
            with patch("src.vector_store.bm25_search", new_callable=AsyncMock, return_value=sparse_hits):
                results = await hybrid_search("proj-1", "query", k=3)

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_score_is_weighted_combination(self) -> None:
        dense_hits = [make_hit("test content", 1.0, "dense")]
        sparse_hits = [make_hit("test content", 1.0, "sparse")]

        with patch("src.vector_store.dense_search", new_callable=AsyncMock, return_value=dense_hits):
            with patch("src.vector_store.bm25_search", new_callable=AsyncMock, return_value=sparse_hits):
                results = await hybrid_search("proj-1", "test", k=1, alpha=0.7)

        assert len(results) == 1
        assert results[0]["score"] == pytest.approx(0.7 * 1.0 + 0.3 * 1.0, abs=0.01)


# ─── rerank ───────────────────────────────────────────────────────────────────

class TestRerank:
    @pytest.mark.asyncio
    async def test_reranks_with_cross_encoder(self) -> None:
        hits = [
            make_hit("relevant content about topic", 0.5),
            make_hit("unrelated general text here", 0.8),
            make_hit("another relevant paragraph", 0.6),
        ]
        mock_reranker = MagicMock()
        mock_reranker.predict = MagicMock(return_value=[0.9, 0.1, 0.7])

        with patch("src.vector_store._get_reranker", return_value=mock_reranker):
            result = await rerank("topic query", hits, top_k=2)

        assert len(result) <= 2
        assert result[0]["content"] == "relevant content about topic"
        for r in result:
            assert "rerank_score" in r

    @pytest.mark.asyncio
    async def test_rerank_no_reranker_returns_top_k(self) -> None:
        hits = [make_hit(f"content {i}", float(i) * 0.1) for i in range(5)]

        with patch("src.vector_store._get_reranker", return_value=None):
            result = await rerank("query", hits, top_k=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rerank_empty_hits(self) -> None:
        result = await rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_adds_rerank_score(self) -> None:
        hits = [make_hit("test text", 0.5)]
        mock_reranker = MagicMock()
        mock_reranker.predict = MagicMock(return_value=[0.8])

        with patch("src.vector_store._get_reranker", return_value=mock_reranker):
            result = await rerank("test", hits, top_k=1)

        assert result[0]["rerank_score"] == pytest.approx(0.8)
