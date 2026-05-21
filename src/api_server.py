"""FastAPI application with all routes."""

import asyncio
import json
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics import export_analytics_csv, get_project_analytics, record_usage
from src.auth import generate_api_key, get_api_key_project, hash_api_key
from src.chatbot_engine import rag_answer_stream, simple_chat_stream
from src.config import settings
from src.database import get_db, init_db
from src.document_processor import get_file_type, parse_file, process_document, process_url
from src.embed_generator import (
    generate_iframe_tag,
    generate_script_tag,
    generate_widget_js,
)
from src.export import (
    export_conversation_json,
    export_conversation_markdown,
    export_conversation_txt,
    export_project,
    import_project,
)
from src.models import ApiKey, Chunk, Conversation, Document, Message, Project, Usage
from src.schemas import (
    ApiKeyCreate,
    ApiKeyResponse,
    ChatRequest,
    ConversationResponse,
    DocumentResponse,
    EmbedCodeResponse,
    EmbedRequest,
    EmbedStatus,
    HealthResponse,
    MessageOut,
    ProjectCreate,
    ProjectResponse,
    ProjectStats,
    ProjectUpdate,
    URLIngestRequest,
    WidgetConfig,
)
from src.streaming import stream_with_sources
from src.vector_store import (
    build_bm25_index,
    delete_chunks_by_document,
    get_collection_stats,
    upsert_chunks,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("database_initialized")
    yield
    logger.info("server_shutdown")


app = FastAPI(
    title="AI Chatbot Builder Pro",
    version="1.0.0",
    description="Production-grade AI chatbot builder with RAG",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    db_ok = False
    chroma_ok = False
    try:
        await db.execute(select(func.now()))
        db_ok = True
    except Exception:
        pass
    try:
        from src.vector_store import _get_chroma_client
        _get_chroma_client()
        chroma_ok = True
    except Exception:
        pass
    return HealthResponse(
        status="ok",
        version="1.0.0",
        db_connected=db_ok,
        chroma_connected=chroma_ok,
    )


# ─── Projects ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/projects", response_model=list[ProjectResponse], tags=["Projects"])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[ProjectResponse]:
    result = await db.execute(
        select(Project).where(Project.is_active == True).order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()
    responses = []
    for p in projects:
        stats = await _get_project_stats(db, p.id)
        resp = ProjectResponse.model_validate(p)
        resp.stats = stats
        responses.append(resp)
    return responses


@app.post("/api/v1/projects", response_model=ProjectResponse, status_code=201, tags=["Projects"])
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)) -> ProjectResponse:
    project = Project(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        model_config_json=data.model_config_data.model_dump(),
        chunking_config_json=data.chunking_config_data.model_dump(),
        embedding_provider=data.embedding_provider,
        embedding_model=data.embedding_model,
        llm_provider=data.llm_provider,
        llm_model=data.llm_model,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    resp = ProjectResponse.model_validate(project)
    resp.stats = ProjectStats()
    return resp


@app.get("/api/v1/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)) -> ProjectResponse:
    project = await _require_project(db, project_id)
    stats = await _get_project_stats(db, project_id)
    resp = ProjectResponse.model_validate(project)
    resp.stats = stats
    return resp


@app.put("/api/v1/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
async def update_project(
    project_id: str, data: ProjectUpdate, db: AsyncSession = Depends(get_db)
) -> ProjectResponse:
    project = await _require_project(db, project_id)
    for field, value in data.model_dump(exclude_none=True).items():
        if field == "model_config_data":
            project.model_config_json = value
        elif field == "chunking_config_data":
            project.chunking_config_json = value
        else:
            setattr(project, field, value)
    project.updated_at = datetime.utcnow()
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@app.delete("/api/v1/projects/{project_id}", response_model=MessageOut, tags=["Projects"])
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)) -> MessageOut:
    project = await _require_project(db, project_id)
    project.is_active = False
    db.add(project)
    return MessageOut(message="Project deleted")


@app.post("/api/v1/projects/{project_id}/duplicate", response_model=ProjectResponse, tags=["Projects"])
async def duplicate_project(project_id: str, db: AsyncSession = Depends(get_db)) -> ProjectResponse:
    original = await _require_project(db, project_id)
    new_project = Project(
        id=str(uuid.uuid4()),
        name=f"{original.name} (copy)",
        description=original.description,
        system_prompt=original.system_prompt,
        model_config_json=original.model_config_json,
        chunking_config_json=original.chunking_config_json,
        embedding_provider=original.embedding_provider,
        embedding_model=original.embedding_model,
        llm_provider=original.llm_provider,
        llm_model=original.llm_model,
    )
    db.add(new_project)
    await db.flush()
    await db.refresh(new_project)
    resp = ProjectResponse.model_validate(new_project)
    resp.stats = ProjectStats()
    return resp


# ─── Documents ────────────────────────────────────────────────────────────────

@app.get("/api/v1/projects/{project_id}/documents", response_model=list[DocumentResponse], tags=["Documents"])
async def list_documents(project_id: str, db: AsyncSession = Depends(get_db)) -> list[DocumentResponse]:
    await _require_project(db, project_id)
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
    )
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@app.post("/api/v1/projects/{project_id}/documents", response_model=DocumentResponse, status_code=201, tags=["Documents"])
async def upload_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    project = await _require_project(db, project_id)

    if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    safe_name = Path(file.filename or "upload").name
    dest_dir = Path(settings.uploads_dir) / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{uuid.uuid4()}_{safe_name}"

    content = await file.read()
    dest_path.write_bytes(content)

    doc = Document(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename=dest_path.name,
        original_filename=safe_name,
        file_type=get_file_type(safe_name),
        file_path=str(dest_path),
        file_size=len(content),
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    chunking_config = project.chunking_config_json or {}
    background_tasks.add_task(_process_document_task, doc.id, project_id, str(dest_path), safe_name, chunking_config)

    return DocumentResponse.model_validate(doc)


@app.post("/api/v1/projects/{project_id}/ingest-url", response_model=DocumentResponse, status_code=201, tags=["Documents"])
async def ingest_url(
    project_id: str,
    data: URLIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    project = await _require_project(db, project_id)

    doc = Document(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename=f"url_{uuid.uuid4().hex[:8]}",
        original_filename=data.url[:100],
        file_type="url",
        source_url=data.url,
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    chunking_config = project.chunking_config_json or {}
    background_tasks.add_task(
        _process_url_task, doc.id, project_id, data.url, data.use_playwright, chunking_config
    )

    return DocumentResponse.model_validate(doc)


@app.get("/api/v1/projects/{project_id}/documents/{doc_id}", response_model=DocumentResponse, tags=["Documents"])
async def get_document(project_id: str, doc_id: str, db: AsyncSession = Depends(get_db)) -> DocumentResponse:
    doc = await _require_document(db, project_id, doc_id)
    return DocumentResponse.model_validate(doc)


@app.delete("/api/v1/projects/{project_id}/documents/{doc_id}", response_model=MessageOut, tags=["Documents"])
async def delete_document(
    project_id: str, doc_id: str, db: AsyncSession = Depends(get_db)
) -> MessageOut:
    doc = await _require_document(db, project_id, doc_id)

    if doc.file_path and Path(doc.file_path).exists():
        Path(doc.file_path).unlink(missing_ok=True)

    await delete_chunks_by_document(project_id, doc_id)
    await db.delete(doc)
    return MessageOut(message="Document deleted")


@app.post("/api/v1/projects/{project_id}/documents/{doc_id}/reprocess", response_model=DocumentResponse, tags=["Documents"])
async def reprocess_document(
    project_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    doc = await _require_document(db, project_id, doc_id)
    project = await _require_project(db, project_id)

    doc.status = "pending"
    doc.error_message = None
    db.add(doc)
    await db.flush()

    chunking_config = project.chunking_config_json or {}
    if doc.file_path:
        background_tasks.add_task(
            _process_document_task, doc.id, project_id, doc.file_path, doc.original_filename, chunking_config
        )
    elif doc.source_url:
        background_tasks.add_task(
            _process_url_task, doc.id, project_id, doc.source_url, False, chunking_config
        )

    return DocumentResponse.model_validate(doc)


@app.get("/api/v1/projects/{project_id}/documents/{doc_id}/chunks", tags=["Documents"])
async def get_document_chunks(
    project_id: str,
    doc_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_document(db, project_id, doc_id)
    total = await db.scalar(
        select(func.count(Chunk.id)).where(Chunk.document_id == doc_id)
    ) or 0
    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == doc_id)
        .order_by(Chunk.chunk_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    chunks = result.scalars().all()
    return {
        "items": [
            {
                "id": c.id,
                "content": c.content,
                "chunk_index": c.chunk_index,
                "token_count": c.token_count,
                "metadata": c.chunk_metadata,
            }
            for c in chunks
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


# ─── Embedding ────────────────────────────────────────────────────────────────

@app.post("/api/v1/projects/{project_id}/embed", response_model=MessageOut, tags=["Embedding"])
async def start_embedding(
    project_id: str,
    data: EmbedRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    project = await _require_project(db, project_id)
    background_tasks.add_task(
        _embed_project_task,
        project_id,
        project.embedding_provider,
        project.embedding_model,
        data.document_ids,
        data.force_reembed,
    )
    return MessageOut(message="Embedding started")


@app.get("/api/v1/projects/{project_id}/embed/status", response_model=EmbedStatus, tags=["Embedding"])
async def get_embed_status(project_id: str, db: AsyncSession = Depends(get_db)) -> EmbedStatus:
    await _require_project(db, project_id)
    result = await db.execute(
        select(Document.status, func.count(Document.id))
        .where(Document.project_id == project_id)
        .group_by(Document.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return EmbedStatus(
        total=sum(counts.values()),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        pending=counts.get("pending", 0),
        in_progress=counts.get("processing", 0),
    )


@app.get("/api/v1/projects/{project_id}/vector-stats", tags=["Embedding"])
async def get_vector_stats(project_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    await _require_project(db, project_id)
    return await get_collection_stats(project_id)


# ─── Chat ─────────────────────────────────────────────────────────────────────

@app.post("/api/v1/projects/{project_id}/chat/stream", tags=["Chat"])
async def chat_stream(
    project_id: str,
    data: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    project = await _require_project(db, project_id)
    model_cfg = project.model_config_json or {}

    conversation_id = data.conversation_id
    if not conversation_id:
        conv = Conversation(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=data.message[:50],
        )
        db.add(conv)
        await db.flush()
        conversation_id = conv.id
    else:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.project_id == project_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Conversation not found")

    history = await _get_conversation_history(db, conversation_id)

    start_time = time.time()
    msg_id = str(uuid.uuid4())

    doc_count = await db.scalar(
        select(func.count(Document.id)).where(
            Document.project_id == project_id, Document.status == "completed"
        )
    ) or 0

    if doc_count > 0:
        stream_gen, sources, est_tokens_in = await rag_answer_stream(
            project_id=project_id,
            query=data.message,
            conversation_history=history,
            system_prompt=project.system_prompt,
            llm_provider=project.llm_provider,
            llm_model=project.llm_model,
            embedding_provider=project.embedding_provider,
            embedding_model=project.embedding_model,
            max_context_chunks=data.max_context_chunks,
            temperature=float(model_cfg.get("temperature", 0.7)),
            max_tokens=int(model_cfg.get("max_tokens", 2048)),
        )
        sources_payload = sources if data.include_sources else []
    else:
        stream_gen = await simple_chat_stream(
            query=data.message,
            conversation_history=history,
            system_prompt=project.system_prompt,
            llm_provider=project.llm_provider,
            llm_model=project.llm_model,
            temperature=float(model_cfg.get("temperature", 0.7)),
            max_tokens=int(model_cfg.get("max_tokens", 2048)),
        )
        sources_payload = []
        est_tokens_in = len(data.message) // 4

    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=data.message,
        tokens_input=est_tokens_in,
    )
    db.add(user_msg)
    await db.flush()

    full_content_store: list[str] = []

    async def _collecting_stream():
        async for chunk in stream_gen:
            full_content_store.append(chunk)
            yield chunk

    async def _finalize():
        content = "".join(full_content_store)
        elapsed_ms = int((time.time() - start_time) * 1000)
        tokens_out = len(content) // 4

        from src.database import db_session
        async with db_session() as session:
            bot_msg = Message(
                id=msg_id,
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                sources=[s if isinstance(s, dict) else s for s in sources_payload],
                tokens_output=tokens_out,
                latency_ms=elapsed_ms,
            )
            session.add(bot_msg)

            conv_result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = conv_result.scalar_one_or_none()
            if conv:
                conv.message_count += 2
                conv.total_tokens += est_tokens_in + tokens_out
                conv.updated_at = datetime.utcnow()
                session.add(conv)

            await record_usage(
                session,
                project_id=project_id,
                tokens_input=est_tokens_in,
                tokens_output=tokens_out,
                latency_ms=elapsed_ms,
                provider=project.llm_provider,
                model=project.llm_model,
                conversation_id=conversation_id,
            )

    sources_for_stream = [
        {
            "document_id": s.get("document_id", ""),
            "document_name": s.get("document_name", ""),
            "chunk_index": s.get("chunk_index", 0),
            "content": s.get("content", ""),
            "score": s.get("score", 0.0),
        }
        for s in sources_payload
    ]

    background_tasks.add_task(_finalize)

    return StreamingResponse(
        stream_with_sources(_collecting_stream(), sources_for_stream, conversation_id, msg_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": conversation_id,
        },
    )


@app.get("/api/v1/projects/{project_id}/conversations", response_model=list[ConversationResponse], tags=["Chat"])
async def list_conversations(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    await _require_project(db, project_id)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [ConversationResponse.model_validate(c) for c in result.scalars().all()]


@app.get("/api/v1/projects/{project_id}/conversations/{conv_id}", response_model=ConversationResponse, tags=["Chat"])
async def get_conversation(
    project_id: str, conv_id: str, db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.project_id == project_id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()
    resp = ConversationResponse.model_validate(conv)
    from src.schemas import MessageResponse
    resp.messages = [MessageResponse.model_validate(m) for m in messages]
    return resp


@app.delete("/api/v1/projects/{project_id}/conversations/{conv_id}", response_model=MessageOut, tags=["Chat"])
async def delete_conversation(
    project_id: str, conv_id: str, db: AsyncSession = Depends(get_db)
) -> MessageOut:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.project_id == project_id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    return MessageOut(message="Conversation deleted")


@app.get("/api/v1/projects/{project_id}/conversations/{conv_id}/export", tags=["Chat"])
async def export_conversation(
    project_id: str,
    conv_id: str,
    format: str = Query("json", pattern="^(json|txt|markdown)$"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.project_id == project_id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    if format == "json":
        data = await export_conversation_json(db, conv_id)
        return Response(content=json.dumps(data, indent=2), media_type="application/json")
    elif format == "txt":
        text = await export_conversation_txt(db, conv_id)
        return Response(content=text, media_type="text/plain")
    else:
        md = await export_conversation_markdown(db, conv_id)
        return Response(content=md, media_type="text/markdown")


# ─── API Keys ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/projects/{project_id}/api-keys", response_model=list[ApiKeyResponse], tags=["API Keys"])
async def list_api_keys(project_id: str, db: AsyncSession = Depends(get_db)) -> list[ApiKeyResponse]:
    await _require_project(db, project_id)
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.project_id == project_id, ApiKey.is_active == True)
        .order_by(ApiKey.created_at.desc())
    )
    return [ApiKeyResponse.model_validate(k) for k in result.scalars().all()]


@app.post("/api/v1/projects/{project_id}/api-keys", response_model=ApiKeyResponse, status_code=201, tags=["API Keys"])
async def create_api_key(
    project_id: str, data: ApiKeyCreate, db: AsyncSession = Depends(get_db)
) -> ApiKeyResponse:
    await _require_project(db, project_id)
    raw_key, key_prefix, key_hash = generate_api_key()

    api_key = ApiKey(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=data.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        rate_limit_per_minute=data.rate_limit_per_minute,
        rate_limit_per_day=data.rate_limit_per_day,
        allowed_origins=data.allowed_origins,
        expires_at=data.expires_at,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    resp = ApiKeyResponse.model_validate(api_key)
    resp.raw_key = raw_key
    return resp


@app.delete("/api/v1/projects/{project_id}/api-keys/{key_id}", response_model=MessageOut, tags=["API Keys"])
async def revoke_api_key(
    project_id: str, key_id: str, db: AsyncSession = Depends(get_db)
) -> MessageOut:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    db.add(key)
    return MessageOut(message="API key revoked")


# ─── Embed Widget ─────────────────────────────────────────────────────────────

@app.post("/api/v1/projects/{project_id}/embed-widget", response_model=EmbedCodeResponse, tags=["Widget"])
async def generate_embed_code(
    project_id: str,
    widget_config: WidgetConfig,
    db: AsyncSession = Depends(get_db),
) -> EmbedCodeResponse:
    await _require_project(db, project_id)
    result = await db.execute(
        select(ApiKey).where(ApiKey.project_id == project_id, ApiKey.is_active == True).limit(1)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=400, detail="No active API key found. Create one first.")

    raw_key = key.key_prefix
    config_dict = widget_config.model_dump()

    return EmbedCodeResponse(
        script_tag=generate_script_tag(raw_key, project_id, config_dict),
        iframe_tag=generate_iframe_tag(raw_key, project_id, config_dict),
        api_endpoint=f"{settings.api_base_url}/api/v1/public/{project_id}",
        widget_config=widget_config,
    )


@app.get("/api/v1/widget.js", tags=["Widget"])
async def serve_widget_js(
    project_id: str = Query(...),
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _require_project(db, project_id)
    config = WidgetConfig().model_dump()
    js = generate_widget_js(api_key, project_id, config)
    return Response(content=js, media_type="application/javascript")


# ─── Public Chat (for embedded widgets) ──────────────────────────────────────

@app.post("/api/v1/public/{project_id}/chat/stream", tags=["Public"])
async def public_chat_stream(
    project_id: str,
    data: ChatRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    from src.auth import get_api_key_project as _get_key_project
    project = await _get_key_project(request, db=db)
    if project.id != project_id:
        raise HTTPException(status_code=403, detail="API key does not match project")

    return await chat_stream(project_id, data, background_tasks, db)


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.get("/api/v1/projects/{project_id}/analytics", tags=["Analytics"])
async def get_analytics(
    project_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_project(db, project_id)
    return await get_project_analytics(db, project_id, days)


@app.get("/api/v1/projects/{project_id}/analytics/export", tags=["Analytics"])
async def export_analytics(
    project_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _require_project(db, project_id)
    analytics = await get_project_analytics(db, project_id, days)
    csv_content = export_analytics_csv(analytics)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="analytics_{project_id}.csv"'},
    )


# ─── Project Export/Import ────────────────────────────────────────────────────

@app.get("/api/v1/projects/{project_id}/export", tags=["Projects"])
async def export_project_endpoint(project_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    await _require_project(db, project_id)
    data = await export_project(db, project_id)
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="project_{project_id}.json"'},
    )


@app.post("/api/v1/projects/import", response_model=ProjectResponse, tags=["Projects"])
async def import_project_endpoint(request: Request, db: AsyncSession = Depends(get_db)) -> ProjectResponse:
    body = await request.json()
    new_id = await import_project(db, body)
    result = await db.execute(select(Project).where(Project.id == new_id))
    project = result.scalar_one()
    resp = ProjectResponse.model_validate(project)
    resp.stats = ProjectStats()
    return resp


# ─── Settings (runtime) ──────────────────────────────────────────────────────

@app.get("/api/v1/settings", tags=["Settings"])
async def get_settings_endpoint() -> dict:
    return {
        "default_llm_provider": settings.default_llm_provider,
        "default_llm_model": settings.default_llm_model,
        "default_embedding_provider": settings.default_embedding_provider,
        "default_embedding_model": settings.default_embedding_model,
        "api_port": settings.api_port,
        "has_openai_key": bool(settings.openai_api_key),
        "has_anthropic_key": bool(settings.anthropic_api_key),
        "has_google_key": bool(settings.google_api_key),
        "has_pinecone_key": bool(settings.pinecone_api_key),
        "ollama_base_url": settings.ollama_base_url,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _require_project(db: AsyncSession, project_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.is_active == True)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _require_document(db: AsyncSession, project_id: str, doc_id: str) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.project_id == project_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def _get_project_stats(db: AsyncSession, project_id: str) -> ProjectStats:
    doc_count = await db.scalar(
        select(func.count(Document.id)).where(Document.project_id == project_id)
    ) or 0
    chunk_count = await db.scalar(
        select(func.count(Chunk.id)).where(Chunk.project_id == project_id)
    ) or 0
    conv_count = await db.scalar(
        select(func.count(Conversation.id)).where(Conversation.project_id == project_id)
    ) or 0
    msg_count = await db.scalar(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.project_id == project_id)
    ) or 0
    token_count = await db.scalar(
        select(func.sum(Document.token_count)).where(Document.project_id == project_id)
    ) or 0
    last_conv = await db.scalar(
        select(func.max(Conversation.updated_at)).where(Conversation.project_id == project_id)
    )
    return ProjectStats(
        doc_count=doc_count,
        chunk_count=chunk_count,
        conversation_count=conv_count,
        message_count=msg_count,
        token_count=int(token_count),
        last_active=last_conv,
    )


async def _get_conversation_history(db: AsyncSession, conversation_id: str) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .limit(40)
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


async def _process_document_task(
    doc_id: str,
    project_id: str,
    file_path: str,
    filename: str,
    chunking_config: dict,
) -> None:
    from src.database import db_session

    async with db_session() as db:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return

        doc.status = "processing"
        db.add(doc)
        await db.flush()

    try:
        raw_text, chunks = await process_document(file_path, filename, chunking_config)

        async with db_session() as db:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if not doc:
                return

            result2 = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result2.scalar_one_or_none()
            embedding_provider = project.embedding_provider if project else "sentence_transformers"
            embedding_model = project.embedding_model if project else "all-MiniLM-L6-v2"

            chunk_objs = []
            for c in chunks:
                chunk_obj = Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    project_id=project_id,
                    content=c["content"],
                    chunk_index=c["chunk_index"],
                    token_count=c["token_count"],
                    chunk_metadata={**c.get("metadata", {}), "document_id": doc_id},
                )
                chunk_objs.append(chunk_obj)
                db.add(chunk_obj)

            await db.flush()

            chroma_chunks = [
                {
                    "content": c.content,
                    "document_id": doc_id,
                    "chunk_index": c.chunk_index,
                    "token_count": c.token_count,
                    "metadata": c.chunk_metadata,
                }
                for c in chunk_objs
            ]
            chroma_ids = await upsert_chunks(
                project_id, chroma_chunks, embedding_provider, embedding_model
            )

            for chunk_obj, chroma_id in zip(chunk_objs, chroma_ids):
                chunk_obj.chroma_id = chroma_id
                db.add(chunk_obj)

            doc.status = "completed"
            doc.chunk_count = len(chunks)
            doc.token_count = sum(c["token_count"] for c in chunks)
            doc.updated_at = datetime.utcnow()
            db.add(doc)

            corpus_texts = [c["content"] for c in chunks]
            corpus_metas = [{"document_id": doc_id, **c.get("metadata", {})} for c in chunks]
            await build_bm25_index(project_id, corpus_texts, corpus_metas)

    except Exception as e:
        logger.error("document_processing_failed", doc_id=doc_id, error=str(e))
        from src.database import db_session
        async with db_session() as db:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                db.add(doc)


async def _process_url_task(
    doc_id: str,
    project_id: str,
    url: str,
    use_playwright: bool,
    chunking_config: dict,
) -> None:
    from src.database import db_session

    async with db_session() as db:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return
        doc.status = "processing"
        db.add(doc)
        await db.flush()

    try:
        raw_text, chunks = await process_url(url, use_playwright, chunking_config)
        await _store_chunks(doc_id, project_id, chunks)
    except Exception as e:
        logger.error("url_processing_failed", doc_id=doc_id, url=url, error=str(e))
        from src.database import db_session
        async with db_session() as db:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                db.add(doc)


async def _store_chunks(doc_id: str, project_id: str, chunks: list[dict]) -> None:
    from src.database import db_session

    async with db_session() as db:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return

        result2 = await db.execute(select(Project).where(Project.id == project_id))
        project = result2.scalar_one_or_none()
        embedding_provider = project.embedding_provider if project else "sentence_transformers"
        embedding_model = project.embedding_model if project else "all-MiniLM-L6-v2"

        chunk_objs = []
        for c in chunks:
            chunk_obj = Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                project_id=project_id,
                content=c["content"],
                chunk_index=c["chunk_index"],
                token_count=c["token_count"],
                chunk_metadata={**c.get("metadata", {}), "document_id": doc_id},
            )
            chunk_objs.append(chunk_obj)
            db.add(chunk_obj)

        await db.flush()

        chroma_chunks = [
            {
                "content": c.content,
                "document_id": doc_id,
                "chunk_index": c.chunk_index,
                "token_count": c.token_count,
                "metadata": c.chunk_metadata,
            }
            for c in chunk_objs
        ]
        chroma_ids = await upsert_chunks(project_id, chroma_chunks, embedding_provider, embedding_model)

        for chunk_obj, chroma_id in zip(chunk_objs, chroma_ids):
            chunk_obj.chroma_id = chroma_id
            db.add(chunk_obj)

        doc.status = "completed"
        doc.chunk_count = len(chunks)
        doc.token_count = sum(c["token_count"] for c in chunks)
        doc.updated_at = datetime.utcnow()
        db.add(doc)

        corpus_texts = [c["content"] for c in chunks]
        corpus_metas = [{"document_id": doc_id, **c.get("metadata", {})} for c in chunks]
        await build_bm25_index(project_id, corpus_texts, corpus_metas)


async def _embed_project_task(
    project_id: str,
    embedding_provider: str,
    embedding_model: str,
    document_ids: Optional[list[str]],
    force_reembed: bool,
) -> None:
    from src.database import db_session

    async with db_session() as db:
        query = select(Document).where(
            Document.project_id == project_id,
            Document.status == "completed",
        )
        if document_ids:
            query = query.where(Document.id.in_(document_ids))
        result = await db.execute(query)
        documents = result.scalars().all()

        for doc in documents:
            chunk_result = await db.execute(
                select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
            )
            chunks = chunk_result.scalars().all()
            if not chunks:
                continue

            chroma_chunks = [
                {
                    "content": c.content,
                    "document_id": doc.id,
                    "chunk_index": c.chunk_index,
                    "token_count": c.token_count,
                    "metadata": c.chunk_metadata,
                }
                for c in chunks
            ]

            try:
                chroma_ids = await upsert_chunks(
                    project_id, chroma_chunks, embedding_provider, embedding_model
                )
                for chunk_obj, chroma_id in zip(chunks, chroma_ids):
                    chunk_obj.chroma_id = chroma_id
                    db.add(chunk_obj)

                corpus_texts = [c.content for c in chunks]
                corpus_metas = [{"document_id": doc.id} for _ in chunks]
                await build_bm25_index(project_id, corpus_texts, corpus_metas)

            except Exception as e:
                logger.error("embed_task_failed", doc_id=doc.id, error=str(e))
