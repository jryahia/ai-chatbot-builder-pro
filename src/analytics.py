"""Usage tracking, query logging, and stats aggregation."""

import csv
import io
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Conversation, Message, Usage

logger = structlog.get_logger(__name__)


async def record_usage(
    db: AsyncSession,
    project_id: str,
    tokens_input: int,
    tokens_output: int,
    latency_ms: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    endpoint: str = "chat",
) -> None:
    usage = Usage(
        project_id=project_id,
        api_key_id=api_key_id,
        conversation_id=conversation_id,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        latency_ms=latency_ms,
        provider=provider,
        model=model,
        endpoint=endpoint,
    )
    db.add(usage)
    await db.flush()


async def get_project_analytics(
    db: AsyncSession,
    project_id: str,
    days: int = 30,
) -> dict:
    since = datetime.utcnow() - timedelta(days=days)

    # Total conversations
    conv_count = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.project_id == project_id,
            Conversation.created_at >= since,
        )
    ) or 0

    # Total messages
    msg_count = await db.scalar(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.project_id == project_id,
            Message.created_at >= since,
            Message.role == "assistant",
        )
    ) or 0

    # Token usage
    token_result = await db.execute(
        select(
            func.sum(Usage.tokens_input),
            func.sum(Usage.tokens_output),
            func.avg(Usage.latency_ms),
        ).where(
            Usage.project_id == project_id,
            Usage.created_at >= since,
        )
    )
    token_row = token_result.one()
    tokens_in = int(token_row[0] or 0)
    tokens_out = int(token_row[1] or 0)
    avg_latency = float(token_row[2] or 0.0)

    # Daily stats
    daily_stats = await _get_daily_stats(db, project_id, since)

    # Top questions
    top_questions = await _get_top_questions(db, project_id, since)

    # Provider usage
    provider_usage = await _get_provider_usage(db, project_id, since)

    return {
        "total_conversations": conv_count,
        "total_messages": msg_count,
        "total_tokens_input": tokens_in,
        "total_tokens_output": tokens_out,
        "avg_response_time_ms": round(avg_latency, 1),
        "daily_stats": daily_stats,
        "top_questions": top_questions,
        "provider_usage": provider_usage,
    }


async def _get_daily_stats(db: AsyncSession, project_id: str, since: datetime) -> list[dict]:
    result = await db.execute(
        select(
            func.date(Usage.created_at).label("date"),
            func.count(Usage.id).label("conversations"),
            func.sum(Usage.tokens_input + Usage.tokens_output).label("tokens"),
        )
        .where(Usage.project_id == project_id, Usage.created_at >= since)
        .group_by(func.date(Usage.created_at))
        .order_by(func.date(Usage.created_at))
    )
    rows = result.all()

    # Fill in missing days
    stats_map: dict[str, dict] = {}
    for row in rows:
        date_str = str(row.date)
        stats_map[date_str] = {
            "date": date_str,
            "conversations": int(row.conversations or 0),
            "messages": int(row.conversations or 0),
            "tokens": int(row.tokens or 0),
        }

    daily = []
    current = since
    while current <= datetime.utcnow():
        date_str = current.strftime("%Y-%m-%d")
        daily.append(stats_map.get(date_str, {
            "date": date_str,
            "conversations": 0,
            "messages": 0,
            "tokens": 0,
        }))
        current += timedelta(days=1)

    return daily


async def _get_top_questions(
    db: AsyncSession,
    project_id: str,
    since: datetime,
    limit: int = 10,
) -> list[dict]:
    result = await db.execute(
        select(Message.content)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.project_id == project_id,
            Message.created_at >= since,
            Message.role == "user",
        )
        .order_by(Message.created_at.desc())
        .limit(500)
    )
    messages = [r[0] for r in result.all()]

    # Truncate to first 100 chars for grouping
    short = [m[:100].strip() for m in messages]
    counter = Counter(short)

    return [
        {"question": q, "count": c}
        for q, c in counter.most_common(limit)
    ]


async def _get_provider_usage(db: AsyncSession, project_id: str, since: datetime) -> dict[str, int]:
    result = await db.execute(
        select(Usage.provider, func.count(Usage.id).label("count"))
        .where(Usage.project_id == project_id, Usage.created_at >= since, Usage.provider.isnot(None))
        .group_by(Usage.provider)
    )
    return {row.provider: int(row.count) for row in result.all()}


def export_analytics_csv(analytics: dict) -> str:
    """Export analytics data as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["AI Chatbot Builder Pro — Analytics Export"])
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Total Conversations", analytics["total_conversations"]])
    writer.writerow(["Total Messages", analytics["total_messages"]])
    writer.writerow(["Total Tokens (Input)", analytics["total_tokens_input"]])
    writer.writerow(["Total Tokens (Output)", analytics["total_tokens_output"]])
    writer.writerow(["Avg Response Time (ms)", analytics["avg_response_time_ms"]])
    writer.writerow([])

    writer.writerow(["Daily Stats"])
    writer.writerow(["Date", "Conversations", "Messages", "Tokens"])
    for day in analytics.get("daily_stats", []):
        writer.writerow([day["date"], day["conversations"], day["messages"], day["tokens"]])
    writer.writerow([])

    writer.writerow(["Top Questions"])
    writer.writerow(["Question", "Count"])
    for q in analytics.get("top_questions", []):
        writer.writerow([q["question"], q["count"]])

    return output.getvalue()
