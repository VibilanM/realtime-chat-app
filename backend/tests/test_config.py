"""Test suite for config modules (settings, redis, database)."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import redis as redis_config
from app.config.database import get_db
from app.config.settings import Settings, get_settings


def test_settings_and_lru_cache():
    """Test Settings defaults and get_settings caching."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.APP_NAME == "Realtime Chat API"
    assert get_settings() is settings


@pytest.mark.asyncio
async def test_redis_config_lifecycle():
    """Test Redis pool creation, client retrieval, and cleanup."""
    with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool_from_url:
        mock_pool = MagicMock()
        mock_pool.disconnect = AsyncMock()
        mock_pool_from_url.return_value = mock_pool

        # Reset global
        redis_config._redis_pool = None

        pool = redis_config.get_redis_pool()
        assert pool == mock_pool

        client = redis_config.get_redis_client()
        assert client is not None

        # Close
        await redis_config.close_redis()
        mock_pool.disconnect.assert_awaited_once()
        assert redis_config._redis_pool is None

        # Calling close again when pool is None
        await redis_config.close_redis()


@pytest.mark.asyncio
async def test_get_db_commit_flow():
    """Test get_db yields session and commits on normal completion."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    with patch("app.config.database.async_session_factory", mock_factory):
        generator = get_db()
        session = await generator.__anext__()
        assert session == mock_session

        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_get_db_rollback_on_exception():
    """Test get_db rolls back session and re-raises exception."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    with patch("app.config.database.async_session_factory", mock_factory):
        generator = get_db()
        session = await generator.__anext__()
        assert session == mock_session

        with pytest.raises(RuntimeError):
            await generator.athrow(RuntimeError("DB query failed"))

        mock_session.rollback.assert_awaited_once()
