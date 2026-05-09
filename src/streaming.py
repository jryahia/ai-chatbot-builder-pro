"""SSE streaming manager for chat responses."""

import asyncio
import json
from typing import Any, AsyncGenerator, Optional

import structlog

logger = structlog.get_logger(__name__)


def sse_event(data: Any, event: Optional[str] = None, id: Optional[str] = None) -> str:
    """Format a single SSE event."""
    lines = []
    if id:
        lines.append(f"id: {id}")
    if event:
        lines.append(f"event: {event}")
    if isinstance(data, (dict, list)):
        lines.append(f"data: {json.dumps(data)}")
    else:
        lines.append(f"data: {data}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


async def stream_text_chunks(
    generator: AsyncGenerator[str, None],
    conversation_id: str,
    message_id: str,
) -> AsyncGenerator[str, None]:
    """Wrap a text generator in SSE format for streaming chat."""
    full_content = ""
    try:
        async for chunk in generator:
            full_content += chunk
            yield sse_event(
                {"type": "chunk", "content": chunk, "conversation_id": conversation_id},
                event="chunk",
            )
            await asyncio.sleep(0)

        yield sse_event(
            {
                "type": "done",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "full_content": full_content,
            },
            event="done",
        )
    except asyncio.CancelledError:
        yield sse_event({"type": "cancelled"}, event="cancelled")
    except Exception as e:
        logger.error("streaming_error", error=str(e))
        yield sse_event({"type": "error", "message": str(e)}, event="error")


async def stream_with_sources(
    generator: AsyncGenerator[str, None],
    sources: list[dict],
    conversation_id: str,
    message_id: str,
) -> AsyncGenerator[str, None]:
    """Stream chat response then send sources at the end."""
    full_content = ""
    try:
        async for chunk in generator:
            full_content += chunk
            yield sse_event(
                {"type": "chunk", "content": chunk},
                event="chunk",
            )
            await asyncio.sleep(0)

        if sources:
            yield sse_event(
                {"type": "sources", "sources": sources},
                event="sources",
            )

        yield sse_event(
            {
                "type": "done",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "full_content": full_content,
            },
            event="done",
        )
    except asyncio.CancelledError:
        yield sse_event({"type": "cancelled"}, event="cancelled")
    except Exception as e:
        logger.error("streaming_error", error=str(e))
        yield sse_event({"type": "error", "message": str(e)}, event="error")


class StreamBuffer:
    """Buffer for collecting streaming chunks with timeout."""

    def __init__(self, timeout: float = 60.0) -> None:
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self.timeout = timeout
        self.full_content: str = ""

    async def put(self, chunk: str) -> None:
        self.full_content += chunk
        await self._queue.put(chunk)

    async def done(self) -> None:
        await self._queue.put(None)

    async def __aiter__(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                chunk = await asyncio.wait_for(self._queue.get(), timeout=self.timeout)
                if chunk is None:
                    break
                yield chunk
            except asyncio.TimeoutError:
                logger.warning("stream_buffer_timeout")
                break
