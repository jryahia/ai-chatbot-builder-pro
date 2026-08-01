"""Application configuration via Pydantic Settings."""

import base64
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/chatbot_builder.db"

    # Security
    secret_key: str = "dev-secret-key-change-in-production-please"
    encryption_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # LLM Providers
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.2"
    default_llm_provider: str = "anthropic"
    default_llm_model: str = "claude-sonnet-4-6"

    # Embeddings
    default_embedding_provider: str = "sentence_transformers"
    default_embedding_model: str = "all-MiniLM-L6-v2"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_prefix: str = "chatbot_"
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    pinecone_index_name: str = "chatbot-builder"

    # Server
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    log_level: str = "info"
    cors_origins: str = "*"
    flet_port: int = 8550

    # File Storage
    uploads_dir: str = "./data/uploads"
    max_upload_size_mb: int = 100

    # Rate Limiting
    default_rate_limit_per_minute: int = 60
    default_rate_limit_per_day: int = 10000

    # Chunking
    default_chunk_size: int = 1000
    default_chunk_overlap: int = 200
    default_chunking_strategy: str = "recursive"

    @model_validator(mode="after")
    def ensure_directories(self) -> "Settings":
        Path(self.uploads_dir).mkdir(parents=True, exist_ok=True)
        Path(self.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",")]

    def get_fernet(self) -> Optional[Fernet]:
        if not self.encryption_key:
            return None
        try:
            key = self.encryption_key.encode()
            if len(base64.urlsafe_b64decode(key + b"==")) < 32:
                raise ValueError("Encryption key too short")
            return Fernet(key)
        except Exception:
            generated = Fernet.generate_key()
            return Fernet(generated)

    def encrypt_value(self, plaintext: str) -> str:
        fernet = self.get_fernet()
        if not fernet:
            return plaintext
        return fernet.encrypt(plaintext.encode()).decode()

    def decrypt_value(self, ciphertext: str) -> str:
        fernet = self.get_fernet()
        if not fernet:
            return ciphertext
        try:
            return fernet.decrypt(ciphertext.encode()).decode()
        except (InvalidToken, Exception):
            return ciphertext

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.database_url or "postgres" in self.database_url

    @property
    def api_base_url(self) -> str:
        return f"http://localhost:{self.api_port}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def save_api_key(provider: str, api_key: str) -> None:
    """Save an API key to the .env file for the given provider."""
    env_path = Path(".env")
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    env_var = key_map.get(provider)
    if not env_var:
        raise ValueError(f"Unknown provider: {provider}")

    # Read existing .env or start fresh
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    # Update or append the key
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_var}="):
            lines[i] = f'{env_var}="{api_key}"'
            found = True
            break
    if not found:
        lines.append(f'{env_var}="{api_key}"')

    env_path.write_text("\n".join(lines) + "\n")

