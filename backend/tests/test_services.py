"""Test suite for ConversationService, MemberService, and MessageService."""

from datetime import datetime, timezone
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import MemberRole, MessageType
from app.exceptions.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import ConversationCreate
from app.schemas.message import MessageCreate
from app.service.conversation_service import ConversationService
from app.service.member_service import MemberService
from app.service.message_service import MessageService


@pytest.fixture
def mock_db():
    db = MagicMock(spec=AsyncSession)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def user_alice():
    u = User(name="Alice", email="alice@example.com")
    u.id = uuid.uuid4()
    return u


@pytest.fixture
def user_bob():
    u = User(name="Bob", email="bob@example.com")
    u.id = uuid.uuid4()
    return u


# =====================================================================
# ConversationService Tests
# =====================================================================

@pytest.mark.asyncio
async def test_create_conversation_without_extra_members(mock_db, user_alice):
    svc = ConversationService(mock_db)
    dummy_conv = Conversation(name="General", description="General chat", created_by=user_alice.id)
    dummy_conv.id = uuid.uuid4()

    svc.conversation_repo.create = AsyncMock(return_value=dummy_conv)
    svc.member_repo.add_member = AsyncMock()

    payload = ConversationCreate(name="General", description="General chat")
    conv = await svc.create_conversation(payload, user_alice)

    assert conv == dummy_conv
    svc.conversation_repo.create.assert_awaited_once_with(
        name="General", description="General chat", created_by=user_alice.id
    )
    svc.member_repo.add_member.assert_awaited_once_with(
        conversation_id=dummy_conv.id, user_id=user_alice.id, role=MemberRole.OWNER
    )


@pytest.mark.asyncio
async def test_create_conversation_with_extra_members(mock_db, user_alice, user_bob):
    svc = ConversationService(mock_db)
    dummy_conv = Conversation(name="Project", description=None, created_by=user_alice.id)
    dummy_conv.id = uuid.uuid4()

    svc.conversation_repo.create = AsyncMock(return_value=dummy_conv)
    svc.member_repo.add_member = AsyncMock()
    svc.user_repo.get_by_ids = AsyncMock(return_value=[user_alice, user_bob])

    payload = ConversationCreate(name="Project", member_ids=[user_alice.id, user_bob.id])
    conv = await svc.create_conversation(payload, user_alice)

    assert conv == dummy_conv
    assert svc.member_repo.add_member.await_count == 2  # 1 for owner, 1 for bob


@pytest.mark.asyncio
async def test_create_conversation_missing_member_raises_404(mock_db, user_alice):
    svc = ConversationService(mock_db)
    dummy_conv = Conversation(name="Test", created_by=user_alice.id)
    dummy_conv.id = uuid.uuid4()

    svc.conversation_repo.create = AsyncMock(return_value=dummy_conv)
    svc.member_repo.add_member = AsyncMock()
    missing_id = uuid.uuid4()
    svc.user_repo.get_by_ids = AsyncMock(return_value=[user_alice])

    payload = ConversationCreate(name="Test", member_ids=[user_alice.id, missing_id])
    with pytest.raises(NotFoundError) as exc_info:
        await svc.create_conversation(payload, user_alice)
    assert "User" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_conversation_success(mock_db, user_alice):
    svc = ConversationService(mock_db)
    dummy_conv = Conversation(name="Test")
    dummy_conv.id = uuid.uuid4()

    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_member = AsyncMock(return_value=True)

    result = await svc.get_conversation(dummy_conv.id, user_alice)
    assert result == dummy_conv


@pytest.mark.asyncio
async def test_get_conversation_not_found(mock_db, user_alice):
    svc = ConversationService(mock_db)
    svc.conversation_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await svc.get_conversation(uuid.uuid4(), user_alice)


@pytest.mark.asyncio
async def test_get_conversation_forbidden(mock_db, user_alice):
    svc = ConversationService(mock_db)
    dummy_conv = Conversation(name="Secret")
    dummy_conv.id = uuid.uuid4()

    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_member = AsyncMock(return_value=False)

    with pytest.raises(ForbiddenError):
        await svc.get_conversation(dummy_conv.id, user_alice)


@pytest.mark.asyncio
async def test_list_conversations(mock_db, user_alice):
    svc = ConversationService(mock_db)
    svc.conversation_repo.list_by_user = AsyncMock(return_value=[Conversation(name="Room 1")])

    res = await svc.list_conversations(user_alice)
    assert len(res) == 1
    svc.conversation_repo.list_by_user.assert_awaited_once_with(user_alice.id)


# =====================================================================
# MemberService Tests
# =====================================================================

@pytest.mark.asyncio
async def test_get_members_success_and_failures(mock_db, user_alice):
    svc = MemberService(mock_db)
    conv_id = uuid.uuid4()

    # Not found
    svc.conversation_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await svc.get_members(conv_id, user_alice)

    # Forbidden (not a member)
    dummy_conv = Conversation(name="Chat")
    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_member = AsyncMock(return_value=False)
    with pytest.raises(ForbiddenError):
        await svc.get_members(conv_id, user_alice)

    # Success
    svc.member_repo.is_member = AsyncMock(return_value=True)
    svc.member_repo.get_members = AsyncMock(return_value=[ConversationMember()])
    members = await svc.get_members(conv_id, user_alice)
    assert len(members) == 1


@pytest.mark.asyncio
async def test_add_members_validations_and_success(mock_db, user_alice, user_bob):
    svc = MemberService(mock_db)
    conv_id = uuid.uuid4()
    dummy_conv = Conversation(name="Chat")

    # Conversation not found during validation
    svc.conversation_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await svc.add_members(conv_id, [user_bob.id], user_alice)

    # Not admin/owner
    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_admin_or_owner = AsyncMock(return_value=False)
    with pytest.raises(ForbiddenError):
        await svc.add_members(conv_id, [user_bob.id], user_alice)

    # Target user not found
    svc.member_repo.is_admin_or_owner = AsyncMock(return_value=True)
    svc.user_repo.get_by_ids = AsyncMock(return_value=[])
    with pytest.raises(NotFoundError):
        await svc.add_members(conv_id, [user_bob.id], user_alice)

    # Target user already a member
    svc.user_repo.get_by_ids = AsyncMock(return_value=[user_bob])
    svc.member_repo.is_member = AsyncMock(return_value=True)
    with pytest.raises(ConflictError):
        await svc.add_members(conv_id, [user_bob.id], user_alice)

    # Success
    svc.member_repo.is_member = AsyncMock(return_value=False)
    dummy_member = ConversationMember(conversation_id=conv_id, user_id=user_bob.id)
    svc.member_repo.add_member = AsyncMock(return_value=dummy_member)

    added = await svc.add_members(conv_id, [user_bob.id], user_alice)
    assert len(added) == 1
    assert added[0] == dummy_member


@pytest.mark.asyncio
async def test_remove_member_flow(mock_db, user_alice, user_bob):
    svc = MemberService(mock_db)
    conv_id = uuid.uuid4()
    dummy_conv = Conversation(name="Chat")
    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_admin_or_owner = AsyncMock(return_value=True)

    # Member not found
    svc.member_repo.get_member = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await svc.remove_member(conv_id, user_bob.id, user_alice)

    # Prevent removing last owner
    owner_member = ConversationMember(role=MemberRole.OWNER.value)
    svc.member_repo.get_member = AsyncMock(return_value=owner_member)
    svc.member_repo.count_owners = AsyncMock(return_value=1)
    with pytest.raises(ForbiddenError):
        await svc.remove_member(conv_id, user_bob.id, user_alice)

    # Success removing member
    regular_member = ConversationMember(role=MemberRole.MEMBER.value)
    svc.member_repo.get_member = AsyncMock(return_value=regular_member)
    svc.member_repo.remove_member = AsyncMock()
    await svc.remove_member(conv_id, user_bob.id, user_alice)
    svc.member_repo.remove_member.assert_awaited_once_with(conv_id, user_bob.id)


@pytest.mark.asyncio
async def test_update_role_flow(mock_db, user_alice, user_bob):
    svc = MemberService(mock_db)
    conv_id = uuid.uuid4()
    dummy_conv = Conversation(name="Chat")
    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_admin_or_owner = AsyncMock(return_value=True)

    # Member not found
    svc.member_repo.update_role = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await svc.update_role(conv_id, user_bob.id, MemberRole.ADMIN, user_alice)

    # Success
    updated_member = ConversationMember(role=MemberRole.ADMIN.value)
    svc.member_repo.update_role = AsyncMock(return_value=updated_member)
    res = await svc.update_role(conv_id, user_bob.id, MemberRole.ADMIN, user_alice)
    assert res == updated_member


# =====================================================================
# MessageService Tests
# =====================================================================

def test_calculate_read_by_all():
    mock_db = MagicMock(spec=AsyncSession)
    svc = MessageService(mock_db)

    # Empty list
    assert svc.calculate_read_by_all([]) is None

    # Single member
    msg1 = Message(content="Hi")
    msg1.id = uuid.uuid4()
    msg1.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    m1 = ConversationMember(last_read_message=msg1)
    assert svc.calculate_read_by_all([m1]) == msg1

    # Multi-member with one unread member
    m2 = ConversationMember(last_read_message=None)
    assert svc.calculate_read_by_all([m1, m2]) is None

    # Multi-member all read: should return the earliest (slowest) read message
    msg2 = Message(content="Hey")
    msg2.id = uuid.uuid4()
    msg2.created_at = datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)
    m2_read = ConversationMember(last_read_message=msg2)
    assert svc.calculate_read_by_all([m1, m2_read]) == msg1


@pytest.mark.asyncio
async def test_send_message_flow(mock_db, user_alice):
    svc = MessageService(mock_db)
    conv_id = uuid.uuid4()
    dummy_conv = Conversation(name="Chat")

    # Conversation not found
    svc.conversation_repo.get_by_id = AsyncMock(return_value=None)
    payload = MessageCreate(content="Hello", message_type=MessageType.TEXT.value)
    with pytest.raises(NotFoundError):
        await svc.send_message(conv_id, payload, user_alice)

    # Not a member
    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_member = AsyncMock(return_value=False)
    with pytest.raises(ForbiddenError):
        await svc.send_message(conv_id, payload, user_alice)

    # Success
    svc.member_repo.is_member = AsyncMock(return_value=True)

    dummy_msg = Message(
        conversation_id=conv_id,
        sender_id=user_alice.id,
        content="Hello everyone!",
        message_type=MessageType.TEXT.value,
    )
    dummy_msg.id = uuid.uuid4()
    dummy_msg.created_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    svc.message_repo.create = AsyncMock(return_value=dummy_msg)
    svc.member_repo.update_last_read = AsyncMock()
    svc.member_repo.get_members = AsyncMock(return_value=[ConversationMember(last_read_message=dummy_msg)])
    svc.redis_client.publish = AsyncMock()

    msg = await svc.send_message(conv_id, payload, user_alice)

    assert msg == dummy_msg
    mock_db.flush.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
    svc.member_repo.update_last_read.assert_awaited_once_with(conv_id, user_alice.id, dummy_msg.id)
    svc.redis_client.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_messages_flow(mock_db, user_alice):
    svc = MessageService(mock_db)
    conv_id = uuid.uuid4()
    dummy_conv = Conversation(name="Chat")
    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_member = AsyncMock(return_value=True)

    svc.message_repo.list_by_conversation = AsyncMock(return_value=([Message()], None, False))
    messages, next_cursor, has_more = await svc.list_messages(conv_id, user_alice, limit=10)
    assert len(messages) == 1
    assert next_cursor is None
    assert has_more is False


@pytest.mark.asyncio
async def test_mark_as_read_all_cases(mock_db, user_alice):
    svc = MessageService(mock_db)
    conv_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    dummy_conv = Conversation(name="Chat")
    svc.conversation_repo.get_by_id = AsyncMock(return_value=dummy_conv)
    svc.member_repo.is_member = AsyncMock(return_value=True)
    svc.redis_client.publish = AsyncMock()

    # Case 1: Target message not found
    svc.message_repo.get_by_id = AsyncMock(return_value=None)
    assert await svc.mark_as_read(conv_id, msg_id, user_alice) is None

    # Case 2: Target message belongs to different conversation
    other_conv_msg = Message(conversation_id=uuid.uuid4())
    svc.message_repo.get_by_id = AsyncMock(return_value=other_conv_msg)
    assert await svc.mark_as_read(conv_id, msg_id, user_alice) is None

    # Case 3: Member not found in conversation
    target_msg = Message(conversation_id=conv_id)
    target_msg.id = msg_id
    target_msg.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    svc.message_repo.get_by_id = AsyncMock(return_value=target_msg)
    svc.member_repo.get_member = AsyncMock(return_value=None)
    assert await svc.mark_as_read(conv_id, msg_id, user_alice) is None

    # Case 4: Monotonic check - already read a newer message
    newer_msg = Message(conversation_id=conv_id)
    newer_msg.id = uuid.uuid4()
    newer_msg.created_at = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)
    member_rec = ConversationMember(last_read_message_id=newer_msg.id)
    svc.member_repo.get_member = AsyncMock(return_value=member_rec)
    
    # Return target_msg for msg_id, and newer_msg for member.last_read_message_id
    def get_by_id_side_effect(m_id):
        return target_msg if m_id == msg_id else newer_msg

    svc.message_repo.get_by_id = AsyncMock(side_effect=get_by_id_side_effect)
    assert await svc.mark_as_read(conv_id, msg_id, user_alice) is None

    # Case 5: Valid forward read receipt
    older_msg = Message(conversation_id=conv_id)
    older_msg.id = uuid.uuid4()
    older_msg.created_at = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    member_rec.last_read_message_id = older_msg.id

    def get_by_id_side_effect_valid(m_id):
        return target_msg if m_id == msg_id else older_msg

    svc.message_repo.get_by_id = AsyncMock(side_effect=get_by_id_side_effect_valid)
    svc.member_repo.update_last_read = AsyncMock()
    svc.member_repo.get_members = AsyncMock(return_value=[member_rec])

    res = await svc.mark_as_read(conv_id, msg_id, user_alice)
    assert res is not None
    assert res["type"] == "message.read"
    assert res["data"]["message_id"] == str(msg_id)
    svc.member_repo.update_last_read.assert_awaited_once_with(conv_id, user_alice.id, msg_id)
    mock_db.commit.assert_awaited_once()
    svc.redis_client.publish.assert_awaited_once()
