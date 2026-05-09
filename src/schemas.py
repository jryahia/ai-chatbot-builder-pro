"""Pydantic v2 schemas for all API endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── Project schemas ────────────────────────────────────────────────────────

class ModelConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0


class ChunkingConfig(BaseModel):
    strategy: str = "recursive"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: list[str] = ["\n\n", "\n", " ", ""]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_config_data: ModelConfig = Field(default_factory=ModelConfig)
    chunking_config_data: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "all-MiniLM-L6-v2"
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_config_data: Optional[ModelConfig] = None
    chunking_config_data: Optional[ChunkingConfig] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class ProjectStats(BaseModel):
    doc_count: int = 0
    chunk_count: int = 0
    conversation_count: int = 0
    message_count: int = 0
    token_count: int = 0
    last_active: Optional[datetime] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    system_prompt: Optional[str]
    model_config_json: Optional[dict]
    chunking_config_json: Optional[dict]
    embedding_provider: str
    embedding_model: str
    llm_provider: str
    llm_model: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stats: Optional[ProjectStats] = None


# ─── Document schemas ────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    filename: str
    original_filename: str
    file_type: str
    source_url: Optional[str]
    file_size: Optional[int]
    status: str
    error_message: Optional[str]
    chunk_count: int
    token_count: int
    metadata_json: Optional[dict]
    created_at: datetime
    updated_at: datetime


class URLIngestRequest(BaseModel):
    url: str
    use_playwright: bool = False
    max_depth: int = 1


class ChunkPreview(BaseModel):
    id: str
    content: str
    chunk_index: int
    token_count: int
    metadata: Optional[dict]


# ─── Conversation / Message schemas ─────────────────────────────────────────

class MessageSource(BaseModel):
    document_id: str
    document_name: str
    chunk_index: int
    content: str
    score: float


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    stream: bool = True
    max_context_chunks: int = 5
    include_sources: bool = True


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    content: str
    sources: list[MessageSource] = []
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: int = 0


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    sources: Optional[list]
    tokens_input: int
    tokens_output: int
    latency_ms: Optional[int]
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    session_id: Optional[str]
    title: Optional[str]
    message_count: int
    total_tokens: int
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []


# ─── Embedding schemas ───────────────────────────────────────────────────────

class EmbedRequest(BaseModel):
    document_ids: Optional[list[str]] = None
    force_reembed: bool = False


class EmbedStatus(BaseModel):
    total: int
    completed: int
    failed: int
    pending: int
    in_progress: int


# ─── API Key schemas ─────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 10000
    allowed_origins: Optional[list[str]] = None
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    key_prefix: str
    rate_limit_per_minute: int
    rate_limit_per_day: int
    allowed_origins: Optional[list]
    is_active: bool
    total_requests: int
    created_at: datetime
    expires_at: Optional[datetime]
    raw_key: Optional[str] = None


# ─── Widget / Embed schemas ──────────────────────────────────────────────────

class WidgetConfig(BaseModel):
    primary_color: str = "#4f8cff"
    background_color: str = "#1a1d27"
    text_color: str = "#f1f5f9"
    position: str = "bottom-right"
    welcome_message: str = "Hi! How can I help you?"
    placeholder_text: str = "Type a message..."
    bot_name: str = "Assistant"
    suggested_questions: list[str] = []
    show_sources: bool = True
    width: int = 380
    height: int = 600


class EmbedCodeResponse(BaseModel):
    script_tag: str
    iframe_tag: str
    api_endpoint: str
    widget_config: WidgetConfig


# ─── Analytics schemas ───────────────────────────────────────────────────────

class DailyStats(BaseModel):
    date: str
    conversations: int
    messages: int
    tokens: int


class AnalyticsResponse(BaseModel):
    total_conversations: int
    total_messages: int
    total_tokens_input: int
    total_tokens_output: int
    avg_response_time_ms: float
    daily_stats: list[DailyStats]
    top_questions: list[dict]
    provider_usage: dict[str, int]


# ─── Settings schemas ────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    default_llm_provider: Optional[str] = None
    default_llm_model: Optional[str] = None
    default_embedding_provider: Optional[str] = None
    default_embedding_model: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    db_connected: bool
    chroma_connected: bool


# ─── Generic responses ───────────────────────────────────────────────────────

class MessageOut(BaseModel):
    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int
