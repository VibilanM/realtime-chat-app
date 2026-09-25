from __future__ import annotations

from typing import AsyncGenerator
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config.settings import get_settings

_redis_pool: aioredis.ConnectionPool | None = None

def get_redis_pool() -> aioredis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
    return _redis_pool

def get_redis_client() -> Redis:
    pool = get_redis_pool()
    return aioredis.Redis(connection_pool=pool)

async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None