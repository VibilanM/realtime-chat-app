"""Test suite for main application setup and lifespan event handlers."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from app.main import app, lifespan


@pytest.mark.asyncio
async def test_lifespan_startup_and_clean_shutdown():
    """Test lifespan context manager normal startup and shutdown."""
    with patch("app.main.listen_to_redis", new_callable=AsyncMock) as mock_listener, \
         patch("app.main.close_redis", new_callable=AsyncMock) as mock_close_redis:

        # Make listener wait until cancelled
        async def mock_listen_loop():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                raise

        mock_listener.side_effect = mock_listen_loop

        async with lifespan(app):
            pass

        mock_close_redis.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_shutdown_with_error():
    """Test lifespan shutdown handles unexpected error during listener task cancellation."""
    async def failing_listener():
        raise RuntimeError("Immediate crash in listener")

    with patch("app.main.listen_to_redis", side_effect=failing_listener), \
         patch("app.main.close_redis", new_callable=AsyncMock) as mock_close_redis:

        async with lifespan(app):
            # Allow the failing task to execute and fail
            await asyncio.sleep(0.01)

        mock_close_redis.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_check_endpoint_direct():
    """Test calling health_check handler directly."""
    from app.main import health_check
    resp = await health_check()
    assert resp == {"status": "ok"}

