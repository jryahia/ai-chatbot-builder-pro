"""File parsing, website crawling, and chunking strategies."""

import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiofiles
import httpx
import structlog
import tiktoken

logger = structlog.get_logger(__name__)

_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        try:
            _tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _tokenizer = None
    return _tokenizer


def count_tokens(text: str) -> int:
    enc = _get_tokenizer()
    if enc:
        return len(enc.encode(text))
    return len(text) // 4


# ─── File Parsers ─────────────────────────────────────────────────────────────

def parse_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_markdown(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    try:
        import markdown
        from bs4 import BeautifulSoup
        html = markdown.markdown(content)
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator="\n")
    except Exception:
        return content


def parse_pdf(path: str) -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning("pdf_parse_error", path=path, error=str(e))
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            return "\n\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as e2:
            raise ValueError(f"Could not parse PDF: {e2}") from e2


def parse_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip():
                parts.append(row_text)
    return "\n\n".join(parts)


def parse_html(path: str) -> str:
    from bs4 import BeautifulSoup
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def parse_csv(path: str) -> str:
    import pandas as pd
    try:
        df = pd.read_csv(path)
        return df.to_string(index=False)
    except Exception as e:
        raise ValueError(f"Could not parse CSV: {e}") from e


def parse_json(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps(data, indent=2, ensure_ascii=False)


PARSERS = {
    ".txt": parse_txt,
    ".md": parse_markdown,
    ".markdown": parse_markdown,
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".html": parse_html,
    ".htm": parse_html,
    ".csv": parse_csv,
    ".json": parse_json,
}


def get_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    type_map = {
        ".txt": "text", ".md": "markdown", ".markdown": "markdown",
        ".pdf": "pdf", ".docx": "docx", ".html": "html", ".htm": "html",
        ".csv": "csv", ".json": "json",
    }
    return type_map.get(suffix, "unknown")


async def parse_file(file_path: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    parser = PARSERS.get(suffix)
    if not parser:
        raise ValueError(f"Unsupported file type: {suffix}")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, parser, file_path)


# ─── Website Crawling ─────────────────────────────────────────────────────────

async def crawl_url_simple(url: str) -> str:
    """Fetch and extract text from a URL using trafilatura."""
    import trafilatura

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ChatbotBuilder/1.0)"
        })
        response.raise_for_status()
        html = response.text

    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, lambda: trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    ))

    if not text:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

    return text or ""


async def crawl_url_playwright(url: str) -> str:
    """Fetch JS-rendered pages using Playwright."""
    try:
        from playwright.async_api import async_playwright
        import trafilatura

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, lambda: trafilatura.extract(html))
        return text or ""
    except Exception as e:
        logger.warning("playwright_crawl_failed", url=url, error=str(e))
        return await crawl_url_simple(url)


async def crawl_url(url: str, use_playwright: bool = False) -> str:
    if use_playwright:
        return await crawl_url_playwright(url)
    return await crawl_url_simple(url)


# ─── Chunking Strategies ──────────────────────────────────────────────────────

def chunk_recursive(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: Optional[list[str]] = None,
) -> list[str]:
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(text: str, seps: list[str]) -> list[str]:
        if not seps:
            return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]

        sep = seps[0]
        splits = text.split(sep) if sep else list(text)
        chunks = []
        current = ""

        for split in splits:
            piece = (current + sep + split).strip() if current else split.strip()
            if count_tokens(piece) <= chunk_size:
                current = piece
            else:
                if current:
                    chunks.append(current)
                if count_tokens(split) > chunk_size:
                    chunks.extend(_split(split, seps[1:]))
                    current = ""
                else:
                    current = split

        if current:
            chunks.append(current)
        return chunks

    raw_chunks = _split(text, separators)

    # Add overlap
    result = []
    for i, chunk in enumerate(raw_chunks):
        if i > 0 and chunk_overlap > 0:
            prev_tokens = raw_chunks[i-1].split()
            overlap_words = prev_tokens[-min(chunk_overlap // 5, len(prev_tokens)):]
            chunk = " ".join(overlap_words) + " " + chunk
        result.append(chunk.strip())

    return [c for c in result if c.strip()]


def chunk_by_tokens(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    enc = _get_tokenizer()
    if not enc:
        return chunk_recursive(text, chunk_size, chunk_overlap)

    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)
        chunks.append(chunk_text)
        start += chunk_size - chunk_overlap
    return chunks


def chunk_semantic(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """Group sentences into semantically coherent chunks."""
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return chunk_recursive(text, chunk_size, chunk_overlap)

    chunks = []
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        if current_tokens + sentence_tokens > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Overlap: keep last few sentences
            overlap_sentences = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk
            current_chunk = overlap_sentences.copy()
            current_tokens = sum(count_tokens(s) for s in current_chunk)
        current_chunk.append(sentence)
        current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return [c for c in chunks if c.strip()]


CHUNKING_STRATEGIES = {
    "recursive": chunk_recursive,
    "token": chunk_by_tokens,
    "semantic": chunk_semantic,
}


def chunk_text(
    text: str,
    strategy: str = "recursive",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    **kwargs,
) -> list[str]:
    chunker = CHUNKING_STRATEGIES.get(strategy, chunk_recursive)
    return chunker(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


# ─── Full Processing Pipeline ─────────────────────────────────────────────────

async def process_document(
    file_path: str,
    filename: str,
    chunking_config: dict,
) -> tuple[str, list[dict]]:
    """Parse file and return (full_text, list_of_chunk_dicts)."""
    raw_text = await parse_file(file_path, filename)

    strategy = chunking_config.get("strategy", "recursive")
    chunk_size = int(chunking_config.get("chunk_size", 1000))
    chunk_overlap = int(chunking_config.get("chunk_overlap", 200))

    text_chunks = chunk_text(raw_text, strategy, chunk_size, chunk_overlap)

    chunks = [
        {
            "content": chunk,
            "chunk_index": i,
            "token_count": count_tokens(chunk),
            "metadata": {
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "strategy": strategy,
            },
        }
        for i, chunk in enumerate(text_chunks)
    ]

    return raw_text, chunks


async def process_url(
    url: str,
    use_playwright: bool = False,
    chunking_config: Optional[dict] = None,
) -> tuple[str, list[dict]]:
    """Crawl URL and return (full_text, list_of_chunk_dicts)."""
    if chunking_config is None:
        chunking_config = {}

    raw_text = await crawl_url(url, use_playwright)
    if not raw_text:
        raise ValueError(f"No content extracted from {url}")

    strategy = chunking_config.get("strategy", "recursive")
    chunk_size = int(chunking_config.get("chunk_size", 1000))
    chunk_overlap = int(chunking_config.get("chunk_overlap", 200))

    text_chunks = chunk_text(raw_text, strategy, chunk_size, chunk_overlap)

    chunks = [
        {
            "content": chunk,
            "chunk_index": i,
            "token_count": count_tokens(chunk),
            "metadata": {
                "source_url": url,
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "strategy": strategy,
            },
        }
        for i, chunk in enumerate(text_chunks)
    ]

    return raw_text, chunks
