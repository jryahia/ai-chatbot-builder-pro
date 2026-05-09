"""pytest tests for document processing: file parsing, chunking, and URL crawling."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.document_processor import (
    CHUNKING_STRATEGIES,
    PARSERS,
    chunk_by_tokens,
    chunk_recursive,
    chunk_semantic,
    chunk_text,
    count_tokens,
    crawl_url,
    get_file_type,
    parse_csv,
    parse_html,
    parse_json,
    parse_markdown,
    parse_txt,
    process_document,
    process_url,
)


# ─── count_tokens ─────────────────────────────────────────────────────────────

class TestCountTokens:
    def test_empty_string(self) -> None:
        assert count_tokens("") == 0

    def test_single_word(self) -> None:
        result = count_tokens("hello")
        assert isinstance(result, int)
        assert result > 0

    def test_longer_text(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. " * 10
        result = count_tokens(text)
        assert result > 50

    def test_proportional_to_length(self) -> None:
        short = count_tokens("hello world")
        long = count_tokens("hello world " * 100)
        assert long > short * 5


# ─── get_file_type ────────────────────────────────────────────────────────────

class TestGetFileType:
    def test_txt(self) -> None:
        assert get_file_type("document.txt") == "text"

    def test_markdown(self) -> None:
        assert get_file_type("readme.md") == "markdown"
        assert get_file_type("readme.markdown") == "markdown"

    def test_pdf(self) -> None:
        assert get_file_type("report.pdf") == "pdf"

    def test_docx(self) -> None:
        assert get_file_type("word.docx") == "docx"

    def test_html(self) -> None:
        assert get_file_type("page.html") == "html"
        assert get_file_type("page.htm") == "html"

    def test_csv(self) -> None:
        assert get_file_type("data.csv") == "csv"

    def test_json(self) -> None:
        assert get_file_type("data.json") == "json"

    def test_unknown(self) -> None:
        assert get_file_type("archive.zip") == "unknown"
        assert get_file_type("image.png") == "unknown"

    def test_case_insensitive(self) -> None:
        assert get_file_type("DOCUMENT.TXT") == "text"
        assert get_file_type("REPORT.PDF") == "pdf"


# ─── File Parsers ─────────────────────────────────────────────────────────────

class TestParseTxt:
    def test_basic_content(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Hello, World!\nSecond line.")
            path = f.name
        try:
            result = parse_txt(path)
            assert "Hello, World!" in result
            assert "Second line." in result
        finally:
            os.unlink(path)

    def test_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            path = f.name
        try:
            result = parse_txt(path)
            assert result == ""
        finally:
            os.unlink(path)

    def test_multiline(self) -> None:
        content = "\n".join(f"Line {i}" for i in range(20))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            result = parse_txt(path)
            assert "Line 0" in result
            assert "Line 19" in result
        finally:
            os.unlink(path)


class TestParseMarkdown:
    def test_converts_headers(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Title\n\nSome paragraph text.\n\n## Subtitle\n\nMore text.")
            path = f.name
        try:
            result = parse_markdown(path)
            assert "Title" in result
            assert "Some paragraph text" in result
            assert "Subtitle" in result
        finally:
            os.unlink(path)

    def test_strips_html_tags(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("**bold** and *italic* text")
            path = f.name
        try:
            result = parse_markdown(path)
            assert "bold" in result
            assert "italic" in result
            assert "<strong>" not in result
        finally:
            os.unlink(path)


class TestParseHtml:
    def test_extracts_text(self) -> None:
        html = "<html><body><h1>Title</h1><p>Content here.</p></body></html>"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            path = f.name
        try:
            result = parse_html(path)
            assert "Title" in result
            assert "Content here" in result
        finally:
            os.unlink(path)

    def test_removes_scripts(self) -> None:
        html = "<html><body><script>alert('x');</script><p>Real content.</p></body></html>"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            path = f.name
        try:
            result = parse_html(path)
            assert "Real content" in result
            assert "alert" not in result
        finally:
            os.unlink(path)


class TestParseJson:
    def test_dict_output(self) -> None:
        data: dict[str, Any] = {"key": "value", "num": 42, "list": [1, 2, 3]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            result = parse_json(path)
            assert "key" in result
            assert "value" in result
            assert "42" in result
        finally:
            os.unlink(path)

    def test_nested_structure(self) -> None:
        data = {"outer": {"inner": "deep_value"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            result = parse_json(path)
            assert "deep_value" in result
        finally:
            os.unlink(path)


class TestParseCsv:
    def test_basic_csv(self) -> None:
        csv_content = "name,age,city\nAlice,30,NYC\nBob,25,LA\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            path = f.name
        try:
            result = parse_csv(path)
            assert "Alice" in result
            assert "Bob" in result
            assert "name" in result
        finally:
            os.unlink(path)


# ─── Chunking Strategies ──────────────────────────────────────────────────────

SAMPLE_SHORT_TEXT = "The quick brown fox jumps over the lazy dog."
SAMPLE_LONG_TEXT = (
    "Artificial intelligence is transforming the world. "
    "Machine learning algorithms can now recognize images, understand speech, "
    "and generate human-like text. Deep neural networks have achieved remarkable "
    "results across many domains including computer vision, natural language processing, "
    "and game playing. The rise of large language models has democratized AI capabilities "
    "and enabled new applications that were previously unimaginable. "
) * 30  # ~4500 tokens


class TestChunkRecursive:
    def test_short_text_single_chunk(self) -> None:
        chunks = chunk_recursive(SAMPLE_SHORT_TEXT, chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_long_text_multiple_chunks(self) -> None:
        chunks = chunk_recursive(SAMPLE_LONG_TEXT, chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1

    def test_no_empty_chunks(self) -> None:
        chunks = chunk_recursive(SAMPLE_LONG_TEXT, chunk_size=300, chunk_overlap=50)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_respects_chunk_size_roughly(self) -> None:
        chunks = chunk_recursive(SAMPLE_LONG_TEXT, chunk_size=200, chunk_overlap=20)
        for chunk in chunks:
            token_count = count_tokens(chunk)
            assert token_count <= 400, f"Chunk too large: {token_count} tokens"

    def test_empty_text(self) -> None:
        chunks = chunk_recursive("", chunk_size=500, chunk_overlap=50)
        assert chunks == [] or all(c.strip() == "" for c in chunks)

    def test_custom_separators(self) -> None:
        text = "Section 1. Content A. Section 2. Content B."
        chunks = chunk_recursive(text, chunk_size=10, chunk_overlap=0, separators=[". "])
        assert len(chunks) >= 1


class TestChunkByTokens:
    def test_basic_chunking(self) -> None:
        chunks = chunk_by_tokens(SAMPLE_LONG_TEXT, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1

    def test_no_empty_chunks(self) -> None:
        chunks = chunk_by_tokens(SAMPLE_LONG_TEXT, chunk_size=150, chunk_overlap=20)
        for chunk in chunks:
            assert chunk != ""

    def test_short_text(self) -> None:
        chunks = chunk_by_tokens(SAMPLE_SHORT_TEXT, chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 1


class TestChunkSemantic:
    def test_splits_into_chunks(self) -> None:
        text = ". ".join(f"Sentence number {i} contains some content" for i in range(50)) + "."
        chunks = chunk_semantic(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) >= 1

    def test_no_empty_chunks(self) -> None:
        text = ". ".join(f"Sentence {i} is here" for i in range(30)) + "."
        chunks = chunk_semantic(text, chunk_size=80, chunk_overlap=10)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_fallback_on_empty(self) -> None:
        chunks = chunk_semantic("", chunk_size=500, chunk_overlap=50)
        assert isinstance(chunks, list)


class TestChunkText:
    def test_recursive_strategy(self) -> None:
        chunks = chunk_text(SAMPLE_LONG_TEXT, strategy="recursive", chunk_size=200, chunk_overlap=20)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_token_strategy(self) -> None:
        chunks = chunk_text(SAMPLE_LONG_TEXT, strategy="token", chunk_size=150, chunk_overlap=20)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_semantic_strategy(self) -> None:
        text = ". ".join(f"Sentence {i} with content" for i in range(40)) + "."
        chunks = chunk_text(text, strategy="semantic", chunk_size=100, chunk_overlap=10)
        assert isinstance(chunks, list)

    def test_unknown_strategy_falls_back(self) -> None:
        chunks = chunk_text(SAMPLE_LONG_TEXT, strategy="nonexistent", chunk_size=200, chunk_overlap=20)
        assert isinstance(chunks, list)

    def test_all_strategies_registered(self) -> None:
        assert "recursive" in CHUNKING_STRATEGIES
        assert "token" in CHUNKING_STRATEGIES
        assert "semantic" in CHUNKING_STRATEGIES


# ─── process_document ─────────────────────────────────────────────────────────

class TestProcessDocument:
    @pytest.mark.asyncio
    async def test_txt_file(self) -> None:
        content = "This is test content. " * 50
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            chunking_config = {"strategy": "recursive", "chunk_size": 200, "chunk_overlap": 20}
            raw_text, chunks = await process_document(path, "test.txt", chunking_config)
            assert "test content" in raw_text
            assert len(chunks) >= 1
            for chunk in chunks:
                assert "content" in chunk
                assert "chunk_index" in chunk
                assert "token_count" in chunk
                assert "metadata" in chunk
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_json_file(self) -> None:
        data = {"records": [{"id": i, "text": f"Record {i}"} for i in range(10)]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            raw_text, chunks = await process_document(
                path, "data.json", {"strategy": "recursive", "chunk_size": 500, "chunk_overlap": 50}
            )
            assert "Record" in raw_text
            assert len(chunks) >= 1
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_chunk_metadata_fields(self) -> None:
        content = "Test content. " * 100
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            _, chunks = await process_document(
                path, "sample.txt", {"strategy": "recursive", "chunk_size": 100, "chunk_overlap": 10}
            )
            for i, chunk in enumerate(chunks):
                assert chunk["chunk_index"] == i
                assert chunk["token_count"] > 0
                assert chunk["metadata"]["filename"] == "sample.txt"
                assert chunk["metadata"]["strategy"] == "recursive"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_unsupported_extension_raises(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                await process_document(path, "file.xyz", {})
        finally:
            os.unlink(path)


# ─── URL Crawling ─────────────────────────────────────────────────────────────

class TestCrawlUrl:
    @pytest.mark.asyncio
    async def test_crawl_simple_with_mock(self) -> None:
        mock_html = """
        <html>
          <body>
            <article>
              <h1>Test Article</h1>
              <p>This is the main content of the article with useful information.</p>
              <p>Second paragraph with more content about the topic.</p>
            </article>
          </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.document_processor.httpx.AsyncClient", return_value=mock_client):
            result = await crawl_url("https://example.com", use_playwright=False)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_crawl_returns_string(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Content</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.document_processor.httpx.AsyncClient", return_value=mock_client):
            result = await crawl_url("https://example.com")
        assert isinstance(result, str)


class TestProcessUrl:
    @pytest.mark.asyncio
    async def test_process_url_returns_chunks(self) -> None:
        long_text = "This is article content. " * 100

        with patch("src.document_processor.crawl_url", new_callable=AsyncMock) as mock_crawl:
            mock_crawl.return_value = long_text
            raw_text, chunks = await process_url(
                "https://example.com",
                use_playwright=False,
                chunking_config={"strategy": "recursive", "chunk_size": 200, "chunk_overlap": 20},
            )

        assert "content" in raw_text
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "content" in chunk
            assert chunk["metadata"]["source_url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_process_url_empty_raises(self) -> None:
        with patch("src.document_processor.crawl_url", new_callable=AsyncMock) as mock_crawl:
            mock_crawl.return_value = ""
            with pytest.raises(ValueError, match="No content extracted"):
                await process_url("https://empty.com")

    @pytest.mark.asyncio
    async def test_process_url_default_chunking_config(self) -> None:
        text = "Article content. " * 50
        with patch("src.document_processor.crawl_url", new_callable=AsyncMock) as mock_crawl:
            mock_crawl.return_value = text
            raw_text, chunks = await process_url("https://example.com")
        assert len(chunks) >= 1


# ─── PARSERS registry ─────────────────────────────────────────────────────────

class TestParsersRegistry:
    def test_all_extensions_registered(self) -> None:
        expected = {".txt", ".md", ".markdown", ".pdf", ".docx", ".html", ".htm", ".csv", ".json"}
        for ext in expected:
            assert ext in PARSERS, f"Extension {ext!r} not in PARSERS"

    def test_all_parsers_callable(self) -> None:
        for ext, parser in PARSERS.items():
            assert callable(parser), f"Parser for {ext!r} is not callable"
