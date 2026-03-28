"""FastAPI dependencies."""
import os
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

def _make_async_url(url: str) -> str:
    """Convert plain postgresql:// URLs (from Render) to postgresql+asyncpg://."""
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )
    return url


DATABASE_URL = _make_async_url(
    os.getenv("DATABASE_URL", "postgresql+asyncpg://farmmap:farmmap@localhost:5433/farmmap")
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_pool: aioredis.Redis | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_pool
