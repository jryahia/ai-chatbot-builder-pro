"""Project export/import and conversation export."""

import json
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Chunk, Conversation, Document, Message, Project

logger = structlog.get_logger(__name__)


# ─── Project Export/Import ────────────────────────────────────────────────────

async def export_project(db: AsyncSession, project_id: str) -> dict:
    """Export a full project to a JSON-serializable dict."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project {project_id} not found")

    doc_result = await db.execute(
        select(Document).where(Document.project_id == project_id)
    )
    documents = doc_result.scalars().all()

    doc_data = []
    for doc in documents:
        chunk_result = await db.execute(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
        )
        chunks = chunk_result.scalars().all()
        doc_data.append({
            "id": doc.id,
            "filename": doc.filename,
            "original_filename": doc.original_filename,
            "file_type": doc.file_type,
            "source_url": doc.source_url,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "token_count": doc.token_count,
            "metadata": doc.metadata_json,
            "created_at": doc.created_at.isoformat(),
            "chunks": [
                {
                    "id": c.id,
                    "content": c.content,
                    "chunk_index": c.chunk_index,
                    "token_count": c.token_count,
                    "metadata": c.chunk_metadata,
                }
                for c in chunks
            ],
        })

    return {
        "export_version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "system_prompt": project.system_prompt,
            "model_config": project.model_config_json,
            "chunking_config": project.chunking_config_json,
            "embedding_provider": project.embedding_provider,
            "embedding_model": project.embedding_model,
            "llm_provider": project.llm_provider,
            "llm_model": project.llm_model,
            "created_at": project.created_at.isoformat(),
        },
        "documents": doc_data,
    }


async def import_project(db: AsyncSession, export_data: dict) -> str:
    """Import a project from exported JSON. Returns new project ID."""
    import uuid

    if export_data.get("export_version") not in ("1.0",):
        raise ValueError("Unsupported export version")

    proj_data = export_data["project"]
    new_project_id = str(uuid.uuid4())

    project = Project(
        id=new_project_id,
        name=f"{proj_data['name']} (imported)",
        description=proj_data.get("description"),
        system_prompt=proj_data.get("system_prompt"),
        model_config_json=proj_data.get("model_config"),
        chunking_config_json=proj_data.get("chunking_config"),
        embedding_provider=proj_data.get("embedding_provider", "sentence_transformers"),
        embedding_model=proj_data.get("embedding_model", "all-MiniLM-L6-v2"),
        llm_provider=proj_data.get("llm_provider", "anthropic"),
        llm_model=proj_data.get("llm_model", "claude-sonnet-4-6"),
    )
    db.add(project)
    await db.flush()

    for doc_data in export_data.get("documents", []):
        new_doc_id = str(uuid.uuid4())
        doc = Document(
            id=new_doc_id,
            project_id=new_project_id,
            filename=doc_data["filename"],
            original_filename=doc_data["original_filename"],
            file_type=doc_data["file_type"],
            source_url=doc_data.get("source_url"),
            status="completed",
            chunk_count=doc_data.get("chunk_count", 0),
            token_count=doc_data.get("token_count", 0),
            metadata_json=doc_data.get("metadata"),
        )
        db.add(doc)
        await db.flush()

        for chunk_data in doc_data.get("chunks", []):
            chunk = Chunk(
                id=str(uuid.uuid4()),
                document_id=new_doc_id,
                project_id=new_project_id,
                content=chunk_data["content"],
                chunk_index=chunk_data["chunk_index"],
                token_count=chunk_data.get("token_count", 0),
                chunk_metadata=chunk_data.get("metadata"),
            )
            db.add(chunk)

    return new_project_id


# ─── Conversation Export ──────────────────────────────────────────────────────

async def export_conversation_json(db: AsyncSession, conversation_id: str) -> dict:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise ValueError(f"Conversation {conversation_id} not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return {
        "conversation_id": conv.id,
        "project_id": conv.project_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "tokens_input": m.tokens_input,
                "tokens_output": m.tokens_output,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


async def export_conversation_txt(db: AsyncSession, conversation_id: str) -> str:
    data = await export_conversation_json(db, conversation_id)
    lines = [
        f"Conversation: {data['title'] or conversation_id}",
        f"Date: {data['created_at']}",
        f"Project: {data['project_id']}",
        "=" * 60,
        "",
    ]
    for msg in data["messages"]:
        role = "You" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
        if msg.get("sources"):
            sources = [s.get("document_name", "Unknown") for s in msg["sources"]]
            lines.append(f"  [Sources: {', '.join(sources)}]")
        lines.append("")
    return "\n".join(lines)


async def export_conversation_markdown(db: AsyncSession, conversation_id: str) -> str:
    data = await export_conversation_json(db, conversation_id)
    lines = [
        f"# {data['title'] or 'Conversation'}",
        f"**Date:** {data['created_at']}",
        "",
    ]
    for msg in data["messages"]:
        if msg["role"] == "user":
            lines.append(f"**You:** {msg['content']}")
        else:
            lines.append(f"**Assistant:** {msg['content']}")
        if msg.get("sources"):
            sources = [f"*{s.get('document_name', 'Unknown')}*" for s in msg["sources"]]
            lines.append(f"> Sources: {', '.join(sources)}")
        lines.append("")
    return "\n".join(lines)
