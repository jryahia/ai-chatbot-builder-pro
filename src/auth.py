"""JWT auth, API key validation, and rate limiting."""

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.models import ApiKey, Project

logger = structlog.get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# In-memory rate limit store: {key_id: {minute_bucket: count, day_bucket: count}}
_rate_store: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


# ─── Password / Hashing ──────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ─── JWT ─────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# ─── API Key Generation ───────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_prefix, key_hash)."""
    prefix = "cbp_"
    raw = prefix + secrets.token_urlsafe(40)
    key_prefix = raw[:16]
    key_hash = hash_api_key(raw)
    return raw, key_prefix, key_hash


# ─── Rate Limiting ────────────────────────────────────────────────────────────

def _minute_bucket() -> str:
    return str(int(time.time() // 60))


def _day_bucket() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def check_rate_limit(key_id: str, limit_per_minute: int, limit_per_day: int) -> None:
    bucket_min = f"min:{_minute_bucket()}"
    bucket_day = f"day:{_day_bucket()}"

    store = _rate_store[key_id]
    store[bucket_min] += 1
    store[bucket_day] += 1

    if store[bucket_min] > limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit_per_minute} requests/minute",
        )
    if store[bucket_day] > limit_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit_per_day} requests/day",
        )

    # Clean up old buckets to prevent memory growth
    current_min = _minute_bucket()
    current_day = _day_bucket()
    stale = [k for k in store if (
        k.startswith("min:") and k != f"min:{current_min}"
    ) or (
        k.startswith("day:") and k != f"day:{current_day}"
    )]
    for k in stale:
        del store[k]


# ─── FastAPI Dependencies ─────────────────────────────────────────────────────

async def get_api_key_project(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Validates API key from header and returns the associated project."""
    raw_key = x_api_key
    if not raw_key:
        # Also check Authorization: Bearer header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            raw_key = auth[7:]

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )

    key_hash = hash_api_key(raw_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # CORS check
    if api_key.allowed_origins:
        origin = request.headers.get("Origin", "")
        if origin and origin not in api_key.allowed_origins and "*" not in api_key.allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin not allowed",
            )

    check_rate_limit(api_key.id, api_key.rate_limit_per_minute, api_key.rate_limit_per_day)

    # Update request count
    api_key.total_requests += 1
    db.add(api_key)

    result = await db.execute(select(Project).where(Project.id == api_key.project_id))
    project = result.scalar_one_or_none()

    if not project or not project.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or inactive",
        )

    return project


async def get_optional_api_key_project(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[Project]:
    try:
        return await get_api_key_project(request, x_api_key, db)
    except HTTPException:
        return None
