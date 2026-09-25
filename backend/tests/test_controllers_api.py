"""Test suite for REST API endpoints and controllers."""

from datetime import datetime, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.constants.enums import MemberRole, MessageType
from app.main import app
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.user import User


@pytest.fixture
def dummy_user():
    user = User(name="Alice", email="alice@example.com")
    user.id = uuid.uuid4()
    user.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    return user


@pytest.fixture
def dummy_conversation(dummy_user):
    conv = Conversation(
        name="General Chat",
        description="General room",
        created_by=dummy_user.id,
    )
    conv.id = uuid.uuid4()
    conv.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    conv.updated_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    return conv


@pytest.fixture
def dummy_member(dummy_user, dummy_conversation):
    member = ConversationMember(
        conversation_id=dummy_conversation.id,
        user_id=dummy_user.id,
        role=MemberRole.OWNER.value,
    )
    member.id = uuid.uuid4()
    member.joined_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    member.user = dummy_user
    member.last_read_message_id = None
    member.last_read_at = None
    return member


@pytest.fixture
def dummy_message(dummy_user, dummy_conversation):
    msg = Message(
        conversation_id=dummy_conversation.id,
        sender_id=dummy_user.id,
        content="Hello world!",
        message_type=MessageType.TEXT.value,
    )
    msg.id = uuid.uuid4()
    msg.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    msg.sender = dummy_user
    return msg


@pytest.mark.asyncio
async def test_health_check():
    """Test health check route."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


from app.config.database import get_db

@pytest.mark.asyncio
async def test_user_controller_list_users(dummy_user):
    """Test GET /api/v1/users endpoint."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [dummy_user]
    mock_session.execute.return_value = mock_result
    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("app.controller.user_controller.get_current_user", return_value=dummy_user), \
         patch("app.controller.user_controller._ensure_dev_users_exist", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/users", headers={"X-User-Id": "alice"})

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_conversation_controller_endpoints(dummy_user, dummy_conversation):
    """Test Conversation CRUD endpoints."""
    with patch("app.auth.auth.get_user_from_username", return_value=dummy_user), \
         patch("app.controller.conversation_controller.ConversationService") as mock_svc_cls:

        mock_svc = mock_svc_cls.return_value
        mock_svc.create_conversation = AsyncMock(return_value=dummy_conversation)
        mock_svc.list_conversations = AsyncMock(return_value=[dummy_conversation])
        mock_svc.get_conversation = AsyncMock(return_value=dummy_conversation)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-User-Id": "alice"}

            # 1. POST /api/v1/conversations
            create_resp = await ac.post(
                "/api/v1/conversations",
                json={"name": "General Chat", "description": "General room"},
                headers=headers,
            )
            assert create_resp.status_code == 201
            assert create_resp.json()["name"] == "General Chat"

            # 2. GET /api/v1/conversations
            list_resp = await ac.get("/api/v1/conversations", headers=headers)
            assert list_resp.status_code == 200
            assert list_resp.json()["count"] == 1

            # 3. GET /api/v1/conversations/{id}
            get_resp = await ac.get(f"/api/v1/conversations/{dummy_conversation.id}", headers=headers)
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == str(dummy_conversation.id)


@pytest.mark.asyncio
async def test_member_controller_endpoints(dummy_user, dummy_conversation, dummy_member):
    """Test Member endpoints: list, add, update role, remove."""
    with patch("app.auth.auth.get_user_from_username", return_value=dummy_user), \
         patch("app.controller.member_controller.MemberService") as mock_svc_cls:

        mock_svc = mock_svc_cls.return_value
        mock_svc.get_members = AsyncMock(return_value=[dummy_member])
        mock_svc.add_members = AsyncMock(return_value=[dummy_member])
        mock_svc.update_role = AsyncMock(return_value=dummy_member)
        mock_svc.remove_member = AsyncMock()

        cid = str(dummy_conversation.id)
        uid = str(dummy_user.id)
        headers = {"X-User-Id": "alice"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. GET members
            get_resp = await ac.get(f"/api/v1/conversations/{cid}/members", headers=headers)
            assert get_resp.status_code == 200
            assert get_resp.json()["count"] == 1

            # 2. POST add members
            add_resp = await ac.post(
                f"/api/v1/conversations/{cid}/members",
                json={"user_ids": [uid]},
                headers=headers,
            )
            assert add_resp.status_code == 201

            # 3. PUT update member role
            update_resp = await ac.put(
                f"/api/v1/conversations/{cid}/members/{uid}",
                json={"role": "admin"},
                headers=headers,
            )
            assert update_resp.status_code == 200

            # 4. DELETE remove member
            del_resp = await ac.delete(
                f"/api/v1/conversations/{cid}/members/{uid}",
                headers=headers,
            )
            assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_message_controller_endpoints(dummy_user, dummy_conversation, dummy_message):
    """Test Message endpoints: send message and list paginated messages."""
    with patch("app.auth.auth.get_user_from_username", return_value=dummy_user), \
         patch("app.controller.message_controller.MessageService") as mock_svc_cls:

        mock_svc = mock_svc_cls.return_value
        mock_svc.send_message = AsyncMock(return_value=dummy_message)
        mock_svc.member_repo.get_members = AsyncMock(return_value=[])
        mock_svc.calculate_read_by_all = MagicMock(return_value=dummy_message)
        mock_svc.list_messages = AsyncMock(return_value=([dummy_message], None, False))

        cid = str(dummy_conversation.id)
        headers = {"X-User-Id": "alice"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. POST send message
            send_resp = await ac.post(
                f"/api/v1/conversations/{cid}/messages",
                json={"content": "Hello world!", "message_type": "text"},
                headers=headers,
            )
            assert send_resp.status_code == 201
            assert send_resp.json()["content"] == "Hello world!"
            assert send_resp.json()["is_read_by_all"] is True

            # 2. GET list messages
            list_resp = await ac.get(
                f"/api/v1/conversations/{cid}/messages?limit=20",
                headers=headers,
            )
            assert list_resp.status_code == 200
            assert len(list_resp.json()["messages"]) == 1
            assert list_resp.json()["has_more"] is False
