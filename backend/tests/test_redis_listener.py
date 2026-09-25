"""Test suite for Redis Pub/Sub listener and background worker loop."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.websocket.redis_listener import listen_to_redis


class AsyncMessageIterator:
    """Async iterator yielding test messages then raising a given exception."""

    def __init__(self, items, terminate_with=None):
        self.items = items
        self.terminate_with = terminate_with
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index < len(self.items):
            item = self.items[self.index]
            self.index += 1
            return item
        if self.terminate_with:
            raise self.terminate_with
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_redis_listener_message_processing():
    """Test Redis listener message decoding and broadcasting branches."""
    test_messages = [
        {"type": "subscribe"},  # Ignored (not pmessage)
        {"type": "pmessage", "data": None, "channel": "conversation:123"},  # Missing data
        {"type": "pmessage", "data": "{}", "channel": None},  # Missing channel
        {"type": "pmessage", "data": "{}", "channel": "malformedchannel"},  # No colon split
        {"type": "pmessage", "data": "invalid-json", "channel": "conversation:conv-1"},  # JSON error
        {
            "type": "pmessage",
            "data": json.dumps({"type": "message.created", "data": {"text": "Hello"}}),
            "channel": "conversation:conv-1",
        },  # Valid payload
    ]

    mock_pubsub = MagicMock()
    mock_pubsub.psubscribe = AsyncMock()
    mock_pubsub.punsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.listen.return_value = AsyncMessageIterator(test_messages, terminate_with=asyncio.CancelledError())

    mock_client = MagicMock()
    mock_client.pubsub.return_value = mock_pubsub

    with patch("app.websocket.redis_listener.get_redis_client", return_value=mock_client), \
         patch("app.websocket.redis_listener.manager.broadcast_to_conversation", new_callable=AsyncMock) as mock_broadcast:

        await listen_to_redis()

        mock_pubsub.psubscribe.assert_awaited_once_with("conversation:*")
        mock_broadcast.assert_awaited_once_with(
            "conv-1",
            {"type": "message.created", "data": {"text": "Hello"}},
        )
        mock_pubsub.punsubscribe.assert_awaited_once_with("conversation:*")
        mock_pubsub.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_listener_broadcast_exception_and_retry_loop():
    """Test handling broadcast exception and retry loop on unexpected failure."""
    valid_msg = {
        "type": "pmessage",
        "data": json.dumps({"type": "ping"}),
        "channel": "conversation:conv-1",
    }

    mock_pubsub_1 = MagicMock()
    mock_pubsub_1.psubscribe = AsyncMock()
    # Trigger exception on close to cover line 78-79
    mock_pubsub_1.close = AsyncMock(side_effect=Exception("Failed closing pubsub"))
    mock_pubsub_1.listen.return_value = AsyncMessageIterator([valid_msg], terminate_with=RuntimeError("Redis connection lost"))

    mock_pubsub_2 = MagicMock()
    mock_pubsub_2.psubscribe = AsyncMock()
    mock_pubsub_2.punsubscribe = AsyncMock()
    # Trigger exception on close during cancel to cover line 69-70
    mock_pubsub_2.close = AsyncMock(side_effect=Exception("Failed closing pubsub on cancel"))
    mock_pubsub_2.listen.return_value = AsyncMessageIterator([], terminate_with=asyncio.CancelledError())

    mock_client = MagicMock()
    mock_client.pubsub.side_effect = [mock_pubsub_1, mock_pubsub_2]

    with patch("app.websocket.redis_listener.get_redis_client", return_value=mock_client), \
         patch("app.websocket.redis_listener.manager.broadcast_to_conversation", new_callable=AsyncMock, side_effect=Exception("Broadcast failed")), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        await listen_to_redis()

        mock_sleep.assert_awaited_once_with(5.0)
        mock_pubsub_1.close.assert_awaited_once()
        mock_pubsub_2.close.assert_awaited_once()
