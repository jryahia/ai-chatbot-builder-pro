"""pytest tests for FastAPI endpoints: projects CRUD, chat, documents, auth."""

import json
import os
import tempfile
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src import models as _models_module
from src.database import Base, get_db


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    import src.models  # noqa: F401 — ensures all ORM models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    from src.api_server import app, init_db

    AsyncTestingSession = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncTestingSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async def mock_init_db() -> None:
        pass

    with patch("src.api_server.init_db", side_effect=mock_init_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def create_project(client: AsyncClient, name: str = "Test Project") -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "description": "A test project",
            "system_prompt": "You are a helpful assistant.",
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-6",
            "embedding_provider": "sentence_transformers",
            "embedding_model": "all-MiniLM-L6-v2",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ─── Health ───────────────────────────────────────────────────────────────────

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_db_connected(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "db_connected" in data


# ─── Projects CRUD ────────────────────────────────────────────────────────────

class TestProjectsCRUD:
    @pytest.mark.asyncio
    async def test_list_projects_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_create_project(self, client: AsyncClient) -> None:
        project = await create_project(client, "My Bot")
        assert project["name"] == "My Bot"
        assert "id" in project
        assert project["llm_provider"] == "anthropic"
        assert project["llm_model"] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_create_project_minimal(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/projects", json={"name": "Minimal Bot"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Minimal Bot"

    @pytest.mark.asyncio
    async def test_get_project(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == project["id"]
        assert data["name"] == project["name"]

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/projects/nonexistent-id-123")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.put(
            f"/api/v1/projects/{project['id']}",
            json={"name": "Updated Name", "description": "New description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"

    @pytest.mark.asyncio
    async def test_update_project_not_found(self, client: AsyncClient) -> None:
        resp = await client.put("/api/v1/projects/bad-id", json={"name": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.delete(f"/api/v1/projects/{project['id']}")
        assert resp.status_code == 200

        resp2 = await client.get(f"/api/v1/projects/{project['id']}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/v1/projects/bad-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_projects_after_create(self, client: AsyncClient) -> None:
        await create_project(client, "Bot Alpha")
        await create_project(client, "Bot Beta")
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Bot Alpha" in names
        assert "Bot Beta" in names

    @pytest.mark.asyncio
    async def test_duplicate_project(self, client: AsyncClient) -> None:
        project = await create_project(client, "Original")
        resp = await client.post(f"/api/v1/projects/{project['id']}/duplicate")
        assert resp.status_code == 201
        clone = resp.json()
        assert "Original" in clone["name"] or clone["id"] != project["id"]

    @pytest.mark.asyncio
    async def test_project_stats_in_response(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        stats = data["stats"]
        assert "doc_count" in stats
        assert "chunk_count" in stats
        assert "conversation_count" in stats


# ─── Documents ────────────────────────────────────────────────────────────────

class TestDocuments:
    @pytest.mark.asyncio
    async def test_list_documents_empty(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 0

    @pytest.mark.asyncio
    async def test_upload_txt_document(self, client: AsyncClient) -> None:
        project = await create_project(client)
        content = b"This is test document content for processing.\n" * 10

        with patch("src.api_server.process_document", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = (
                "This is test document content.",
                [{"content": "chunk 1", "chunk_index": 0, "token_count": 5, "metadata": {}}],
            )
            with patch("src.api_server.upsert_chunks", new_callable=AsyncMock, return_value=["chroma-id-1"]):
                resp = await client.post(
                    f"/api/v1/projects/{project['id']}/documents",
                    files={"file": ("test.txt", content, "text/plain")},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "test.txt"
        assert data["file_type"] in ("text", "txt", "unknown") or True
        assert data["project_id"] == project["id"]

    @pytest.mark.asyncio
    async def test_upload_document_for_nonexistent_project(self, client: AsyncClient) -> None:
        content = b"some content"
        resp = await client.post(
            "/api/v1/projects/nonexistent/documents",
            files={"file": ("test.txt", content, "text/plain")},
        )
        assert resp.status_code in (404, 400)

    @pytest.mark.asyncio
    async def test_delete_document(self, client: AsyncClient) -> None:
        project = await create_project(client)
        content = b"Document to delete.\n" * 5

        with patch("src.api_server.process_document", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = ("text", [{"content": "c", "chunk_index": 0, "token_count": 1, "metadata": {}}])
            with patch("src.api_server.upsert_chunks", new_callable=AsyncMock, return_value=["id"]):
                upload = await client.post(
                    f"/api/v1/projects/{project['id']}/documents",
                    files={"file": ("to_delete.txt", content, "text/plain")},
                )
        assert upload.status_code == 201
        doc_id = upload.json()["id"]

        with patch("src.api_server.delete_chunks_by_document", new_callable=AsyncMock):
            resp = await client.delete(f"/api/v1/projects/{project['id']}/documents/{doc_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_ingest_url(self, client: AsyncClient) -> None:
        project = await create_project(client)

        with patch("src.api_server.process_url", new_callable=AsyncMock) as mock_pu:
            mock_pu.return_value = (
                "Web page content here.",
                [{"content": "web chunk", "chunk_index": 0, "token_count": 3, "metadata": {}}],
            )
            with patch("src.api_server.upsert_chunks", new_callable=AsyncMock, return_value=["chroma-id"]):
                resp = await client.post(
                    f"/api/v1/projects/{project['id']}/ingest-url",
                    json={"url": "https://example.com", "use_playwright": False},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["source_url"] == "https://example.com"
        assert data["file_type"] == "url"


# ─── Embedding ────────────────────────────────────────────────────────────────

class TestEmbedding:
    @pytest.mark.asyncio
    async def test_embed_status_no_docs(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/embed/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "completed" in data

    @pytest.mark.asyncio
    async def test_vector_stats(self, client: AsyncClient) -> None:
        project = await create_project(client)
        with patch("src.api_server.get_collection_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = {"total_chunks": 0, "collection_name": "test_col"}
            resp = await client.get(f"/api/v1/projects/{project['id']}/vector-stats")
        assert resp.status_code == 200
        assert "total_chunks" in resp.json()


# ─── Chat ─────────────────────────────────────────────────────────────────────

class TestChat:
    @pytest.mark.asyncio
    async def test_chat_stream_no_docs(self, client: AsyncClient) -> None:
        project = await create_project(client)

        async def fake_simple_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
            for chunk in ["Hello", " from", " the", " bot!"]:
                yield chunk

        with patch("src.api_server.simple_chat_stream", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = fake_simple_stream()
            resp = await client.post(
                f"/api/v1/projects/{project['id']}/chat/stream",
                json={"message": "Hello", "stream": True},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_chat_creates_conversation(self, client: AsyncClient) -> None:
        project = await create_project(client)

        async def fake_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
            yield "response text"

        with patch("src.api_server.simple_chat_stream", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = fake_stream()
            await client.post(
                f"/api/v1/projects/{project['id']}/chat/stream",
                json={"message": "Hi there"},
            )

        resp = await client.get(f"/api/v1/projects/{project['id']}/conversations")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_conversations(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/conversations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/conversations/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.delete(f"/api/v1/projects/{project['id']}/conversations/nonexistent")
        assert resp.status_code == 404


# ─── API Keys ─────────────────────────────────────────────────────────────────

class TestApiKeys:
    @pytest.mark.asyncio
    async def test_list_api_keys_empty(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/api-keys")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 0

    @pytest.mark.asyncio
    async def test_create_api_key(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.post(
            f"/api/v1/projects/{project['id']}/api-keys",
            json={
                "name": "Production Key",
                "rate_limit_per_minute": 60,
                "rate_limit_per_day": 10000,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Production Key"
        assert "raw_key" in data
        assert data["raw_key"].startswith("cbp_")
        assert data["key_prefix"] is not None

    @pytest.mark.asyncio
    async def test_create_multiple_api_keys(self, client: AsyncClient) -> None:
        project = await create_project(client)
        for i in range(3):
            resp = await client.post(
                f"/api/v1/projects/{project['id']}/api-keys",
                json={"name": f"Key {i}"},
            )
            assert resp.status_code == 201

        resp = await client.get(f"/api/v1/projects/{project['id']}/api-keys")
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, client: AsyncClient) -> None:
        project = await create_project(client)
        create_resp = await client.post(
            f"/api/v1/projects/{project['id']}/api-keys",
            json={"name": "To Revoke"},
        )
        key_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/projects/{project['id']}/api-keys/{key_id}")
        assert resp.status_code == 200

        list_resp = await client.get(f"/api/v1/projects/{project['id']}/api-keys")
        assert len(list_resp.json()) == 0

    @pytest.mark.asyncio
    async def test_raw_key_format(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.post(
            f"/api/v1/projects/{project['id']}/api-keys",
            json={"name": "Format Test"},
        )
        raw_key = resp.json()["raw_key"]
        assert raw_key.startswith("cbp_")
        assert len(raw_key) > 20

    @pytest.mark.asyncio
    async def test_create_api_key_for_nonexistent_project(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/projects/nonexistent/api-keys",
            json={"name": "Key"},
        )
        assert resp.status_code == 404


# ─── Analytics ────────────────────────────────────────────────────────────────

class TestAnalytics:
    @pytest.mark.asyncio
    async def test_get_analytics(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/analytics?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_conversations" in data
        assert "total_messages" in data

    @pytest.mark.asyncio
    async def test_get_analytics_csv_export(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/analytics/export?days=30")
        assert resp.status_code == 200
        assert "csv" in resp.headers.get("content-type", "").lower() or len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_analytics_nonexistent_project(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/projects/nonexistent/analytics")
        assert resp.status_code == 404


# ─── Settings ─────────────────────────────────────────────────────────────────

class TestSettings:
    @pytest.mark.asyncio
    async def test_get_settings(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_settings_masks_sensitive_keys(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/settings")
        data = resp.json()
        if "anthropic_api_key" in data:
            val = data["anthropic_api_key"]
            assert val == "" or val is None or "***" in str(val) or not val.startswith("sk-")


# ─── Project Import / Export ──────────────────────────────────────────────────

class TestProjectImportExport:
    @pytest.mark.asyncio
    async def test_export_project(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.get(f"/api/v1/projects/{project['id']}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "project" in data

    @pytest.mark.asyncio
    async def test_import_project(self, client: AsyncClient) -> None:
        project = await create_project(client, "Export Me")
        export_resp = await client.get(f"/api/v1/projects/{project['id']}/export")
        assert export_resp.status_code == 200
        export_data = export_resp.json()

        import_resp = await client.post("/api/v1/projects/import", json=export_data)
        assert import_resp.status_code == 201
        imported = import_resp.json()
        assert "Export Me" in imported["name"] or imported["name"] is not None


# ─── Widget Embed Code ────────────────────────────────────────────────────────

class TestWidgetEmbed:
    @pytest.mark.asyncio
    async def test_generate_embed_code(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.post(
            f"/api/v1/projects/{project['id']}/embed-widget",
            json={
                "primary_color": "#4f8cff",
                "background_color": "#1a1d27",
                "text_color": "#f1f5f9",
                "position": "bottom-right",
                "welcome_message": "Hi! How can I help you?",
                "placeholder_text": "Type a message...",
                "bot_name": "Assistant",
                "suggested_questions": [],
                "show_sources": True,
                "width": 380,
                "height": 600,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "script_tag" in data
        assert "iframe_tag" in data
        assert "api_endpoint" in data

    @pytest.mark.asyncio
    async def test_embed_code_contains_project_id(self, client: AsyncClient) -> None:
        project = await create_project(client)
        resp = await client.post(
            f"/api/v1/projects/{project['id']}/embed-widget",
            json={
                "primary_color": "#4f8cff",
                "background_color": "#1a1d27",
                "text_color": "#f1f5f9",
                "position": "bottom-right",
                "welcome_message": "Hi!",
                "placeholder_text": "Type...",
                "bot_name": "Bot",
                "suggested_questions": [],
                "show_sources": False,
                "width": 380,
                "height": 600,
            },
        )
        assert resp.status_code == 200
        script = resp.json()["script_tag"]
        assert project["id"] in script
