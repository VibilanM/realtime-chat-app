"""Test suite for WebSocket ConnectionManager demonstrating line coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket

from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def manager():
    """Create a fresh instance of ConnectionManager for each test."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket instance with async methods."""
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_new_conversation(manager, mock_websocket):
    """Test connecting a WebSocket to a new conversation ID."""
    conv_id = "conv-123"
    
    await manager.connect(conv_id, mock_websocket)
    
    # Verify accept was called on the socket
    mock_websocket.accept.assert_awaited_once()
    
    # Verify the socket is stored under the conversation ID
    assert conv_id in manager.active_connections
    assert manager.active_connections[conv_id] == [mock_websocket]


@pytest.mark.asyncio
async def test_connect_existing_conversation(manager, mock_websocket):
    """Test connecting multiple WebSockets to the same conversation ID."""
    conv_id = "conv-123"
    ws2 = MagicMock(spec=WebSocket)
    ws2.accept = AsyncMock()
    
    await manager.connect(conv_id, mock_websocket)
    await manager.connect(conv_id, ws2)
    
    assert len(manager.active_connections[conv_id]) == 2
    assert manager.active_connections[conv_id] == [mock_websocket, ws2]


@pytest.mark.asyncio
async def test_disconnect_removes_socket_and_cleans_up_key(manager, mock_websocket):
    """Test disconnecting the only socket removes the conversation key."""
    conv_id = "conv-123"
    await manager.connect(conv_id, mock_websocket)
    
    manager.disconnect(conv_id, mock_websocket)
    
    # Since the list is now empty, the key should be deleted
    assert conv_id not in manager.active_connections


@pytest.mark.asyncio
async def test_disconnect_keeps_other_sockets(manager, mock_websocket):
    """Test disconnecting one socket retains other connected sockets in the conversation."""
    conv_id = "conv-123"
    ws2 = MagicMock(spec=WebSocket)
    ws2.accept = AsyncMock()
    
    await manager.connect(conv_id, mock_websocket)
    await manager.connect(conv_id, ws2)
    
    manager.disconnect(conv_id, mock_websocket)
    
    assert conv_id in manager.active_connections
    assert manager.active_connections[conv_id] == [ws2]


def test_disconnect_non_existent_conversation_or_socket(manager, mock_websocket):
    """Test disconnecting a non-registered socket does not raise an error."""
    # Disconnect when conversation doesn't exist
    manager.disconnect("non-existent-conv", mock_websocket)
    
    # Disconnect a socket that wasn't registered in an existing conversation
    manager.active_connections["existing-conv"] = []
    manager.disconnect("existing-conv", mock_websocket)
    assert "existing-conv" not in manager.active_connections


@pytest.mark.asyncio
async def test_broadcast_to_conversation_success(manager, mock_websocket):
    """Test broadcasting payload to all active sockets in a conversation."""
    conv_id = "conv-123"
    ws2 = MagicMock(spec=WebSocket)
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()
    
    await manager.connect(conv_id, mock_websocket)
    await manager.connect(conv_id, ws2)
    
    payload = {"type": "message.created", "data": {"text": "Hello world!"}}
    await manager.broadcast_to_conversation(conv_id, payload)
    
    mock_websocket.send_json.assert_awaited_once_with(payload)
    ws2.send_json.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_broadcast_to_empty_or_non_existent_conversation(manager):
    """Test broadcasting to a conversation with no connections does not throw."""
    payload = {"type": "test"}
    # Should safely return without errors
    await manager.broadcast_to_conversation("empty-conv", payload)


@pytest.mark.asyncio
async def test_broadcast_handles_and_cleans_up_broken_connections(manager, mock_websocket):
    """Test that failed/broken sockets are removed during broadcast."""
    conv_id = "conv-123"
    healthy_ws = MagicMock(spec=WebSocket)
    healthy_ws.accept = AsyncMock()
    healthy_ws.send_json = AsyncMock()
    
    # Make mock_websocket raise an exception when sending
    mock_websocket.send_json.side_effect = RuntimeError("Socket disconnected")
    
    await manager.connect(conv_id, mock_websocket)
    await manager.connect(conv_id, healthy_ws)
    
    payload = {"type": "message.created", "data": {"text": "Hello!"}}
    await manager.broadcast_to_conversation(conv_id, payload)
    
    # Healthy socket received the message
    healthy_ws.send_json.assert_awaited_once_with(payload)
    
    # Broken socket was pruned from active connections
    assert manager.active_connections[conv_id] == [healthy_ws]
