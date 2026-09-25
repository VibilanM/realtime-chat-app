"""Test suite for WebSocket endpoint routes demonstrating 100% line coverage."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect, status

from app.models.conversation import Conversation
from app.models.user import User
from app.websocket.websocket_routes import websocket_endpoint


@pytest.fixture
def mock_ws():
    """Mock FastAPI WebSocket object."""
    ws = MagicMock(spec=WebSocket)
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy AsyncSession."""
    return MagicMock()


@pytest.fixture
def dummy_user():
    user = User(name="Alice", email="alice@example.com")
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def dummy_conversation():
    conv = Conversation(name="General Chat")
    conv.id = uuid.uuid4()
    return conv


@pytest.mark.asyncio
async def test_websocket_invalid_uuid(mock_ws, mock_db):
    """Test rejecting websocket connection with invalid conversation UUID."""
    await websocket_endpoint(mock_ws, "not-a-valid-uuid", "alice", mock_db)
    mock_ws.close.assert_awaited_once_with(
        code=status.WS_1008_POLICY_VIOLATION,
        reason="Invalid conversation ID format",
    )


@pytest.mark.asyncio
async def test_websocket_auth_failure(mock_ws, mock_db):
    """Test rejecting websocket connection when user authentication fails."""
    conv_id = str(uuid.uuid4())
    with patch("app.websocket.websocket_routes.get_user_from_username", side_effect=Exception("Invalid user")):
        await websocket_endpoint(mock_ws, conv_id, "unknown", mock_db)
        mock_ws.close.assert_awaited_once_with(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication failed",
        )


@pytest.mark.asyncio
async def test_websocket_conversation_not_found(mock_ws, mock_db, dummy_user):
    """Test rejecting websocket connection when conversation does not exist."""
    conv_id = str(uuid.uuid4())
    with patch("app.websocket.websocket_routes.get_user_from_username", return_value=dummy_user), \
         patch("app.websocket.websocket_routes.ConversationRepository.get_by_id", return_value=None):
        await websocket_endpoint(mock_ws, conv_id, "alice", mock_db)
        mock_ws.close.assert_awaited_once_with(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Conversation not found",
        )


@pytest.mark.asyncio
async def test_websocket_not_a_member(mock_ws, mock_db, dummy_user, dummy_conversation):
    """Test rejecting websocket when user is not a member of the conversation."""
    conv_id = str(dummy_conversation.id)
    with patch("app.websocket.websocket_routes.get_user_from_username", return_value=dummy_user), \
         patch("app.websocket.websocket_routes.ConversationRepository.get_by_id", return_value=dummy_conversation), \
         patch("app.websocket.websocket_routes.MemberRepository.is_member", return_value=False):
        await websocket_endpoint(mock_ws, conv_id, "alice", mock_db)
        mock_ws.close.assert_awaited_once_with(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Not a member of this conversation",
        )


@pytest.mark.asyncio
async def test_websocket_connection_and_read_receipt_flow(mock_ws, mock_db, dummy_user, dummy_conversation):
    """Test successful websocket connection, connected frame, processing message.read, and disconnect."""
    conv_id = str(dummy_conversation.id)
    target_msg_id = str(uuid.uuid4())

    # Simulate messages sent by client: empty, invalid json, other event, missing id, invalid uuid, valid read receipt, then disconnect
    mock_ws.receive_text.side_effect = [
        "",  # empty whitespace
        "invalid-json-text",  # decode error
        json.dumps({"type": "ping"}),  # unrelated event
        json.dumps({"type": "message.read"}),  # missing messageId
        json.dumps({"type": "message.read", "messageId": "not-uuid"}),  # invalid uuid
        json.dumps({"type": "message.read", "messageId": target_msg_id}),  # valid read receipt
        WebSocketDisconnect(),  # disconnect
    ]

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session_factory.return_value.__aexit__.return_value = None

    with patch("app.websocket.websocket_routes.get_user_from_username", return_value=dummy_user), \
         patch("app.websocket.websocket_routes.ConversationRepository.get_by_id", return_value=dummy_conversation), \
         patch("app.websocket.websocket_routes.MemberRepository.is_member", return_value=True), \
         patch("app.websocket.websocket_routes.manager.connect", new_callable=AsyncMock) as mock_connect, \
         patch("app.websocket.websocket_routes.manager.disconnect") as mock_disconnect, \
         patch("app.websocket.websocket_routes.async_session_factory", mock_session_factory), \
         patch("app.websocket.websocket_routes.MessageService") as mock_svc_cls:

        mock_svc = mock_svc_cls.return_value
        mock_svc.mark_as_read = AsyncMock()

        await websocket_endpoint(mock_ws, conv_id, "alice", mock_db)

        # Verify connected
        mock_connect.assert_awaited_once_with(conv_id, mock_ws)
        mock_ws.send_json.assert_awaited_once_with({
            "type": "connected",
            "event": "connected",
            "data": {
                "conversation_id": conv_id,
                "user": "alice",
                "user_id": str(dummy_user.id),
            },
        })

        # Verify mark_as_read was called for valid read receipt
        mock_svc.mark_as_read.assert_awaited_once_with(
            conversation_id=dummy_conversation.id,
            message_id=uuid.UUID(target_msg_id),
            user=dummy_user,
        )

        # Verify disconnected
        mock_disconnect.assert_called_once_with(conv_id, mock_ws)


@pytest.mark.asyncio
async def test_websocket_error_handling_in_loop(mock_ws, mock_db, dummy_user, dummy_conversation):
    """Test unexpected exception handling in websocket loop."""
    conv_id = str(dummy_conversation.id)
    target_msg_id = str(uuid.uuid4())

    mock_ws.receive_text.side_effect = [
        json.dumps({"type": "message.read", "messageId": target_msg_id}),
        RuntimeError("Unexpected socket crash"),
    ]

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session_factory.return_value.__aexit__.return_value = None

    with patch("app.websocket.websocket_routes.get_user_from_username", return_value=dummy_user), \
         patch("app.websocket.websocket_routes.ConversationRepository.get_by_id", return_value=dummy_conversation), \
         patch("app.websocket.websocket_routes.MemberRepository.is_member", return_value=True), \
         patch("app.websocket.websocket_routes.manager.connect", new_callable=AsyncMock), \
         patch("app.websocket.websocket_routes.manager.disconnect") as mock_disconnect, \
         patch("app.websocket.websocket_routes.async_session_factory", mock_session_factory), \
         patch("app.websocket.websocket_routes.MessageService") as mock_svc_cls:

        mock_svc = mock_svc_cls.return_value
        # Simulate mark_as_read throwing an error
        mock_svc.mark_as_read = AsyncMock(side_effect=Exception("DB Error"))

        await websocket_endpoint(mock_ws, conv_id, "alice", mock_db)

        # Verify manager disconnected on unexpected crash
        mock_disconnect.assert_called_once_with(conv_id, mock_ws)
