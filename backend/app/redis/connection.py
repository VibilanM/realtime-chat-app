import redis.asyncio as aioredis

from app.config.settings import get_settings

settings = get_settings()

redis_pool: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """Initialize the Redis connection pool."""
    global redis_pool
    redis_pool = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    return redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global redis_pool
    if redis_pool:
        await redis_pool.close()
        redis_pool = None


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency that returns the Redis connection."""
    if redis_pool is None:
        raise RuntimeError("Redis connection not initialized")
    return redis_pool
