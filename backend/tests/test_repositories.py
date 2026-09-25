"""Test suite for data repositories demonstrating 100% line coverage."""

from datetime import datetime, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import MemberRole, MessageType
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture
def mock_db():
    db = MagicMock(spec=AsyncSession)
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


# =====================================================================
# UserRepository Tests
# =====================================================================

@pytest.mark.asyncio
async def test_user_repository_all_methods(mock_db):
    repo = UserRepository(mock_db)
    uid = uuid.uuid4()
    dummy_user = User(name="Alice", email="alice@example.com")
    dummy_user.id = uid

    # 1. create
    created = await repo.create("Alice", "alice@example.com")
    assert created.name == "Alice"
    assert created.email == "alice@example.com"
    mock_db.add.assert_called_with(created)
    mock_db.flush.assert_awaited()

    # 2. get_by_id
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = dummy_user
    mock_db.execute.return_value = mock_res
    user = await repo.get_by_id(uid)
    assert user == dummy_user

    # 3. get_by_email
    mock_res.scalar_one_or_none.return_value = dummy_user
    user = await repo.get_by_email("alice@example.com")
    assert user == dummy_user

    # 4. get_by_ids
    mock_res.scalars.return_value.all.return_value = [dummy_user]
    users = await repo.get_by_ids([uid])
    assert users == [dummy_user]


# =====================================================================
# ConversationRepository Tests
# =====================================================================

@pytest.mark.asyncio
async def test_conversation_repository_all_methods(mock_db):
    repo = ConversationRepository(mock_db)
    cid = uuid.uuid4()
    uid = uuid.uuid4()
    dummy_conv = Conversation(name="General", description="Desc", created_by=uid)
    dummy_conv.id = cid

    # 1. create
    conv = await repo.create("General", uid, "Desc")
    assert conv.name == "General"
    assert conv.created_by == uid
    mock_db.add.assert_called_with(conv)
    mock_db.flush.assert_awaited()

    # 2. get_by_id
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = dummy_conv
    mock_db.execute.return_value = mock_res
    result = await repo.get_by_id(cid)
    assert result == dummy_conv

    # 3. list_by_user
    mock_res.scalars.return_value.all.return_value = [dummy_conv]
    convs = await repo.list_by_user(uid)
    assert convs == [dummy_conv]

    # 4. update
    updated = await repo.update(dummy_conv, name="Updated Name", non_existent_attr="ignored", description=None)
    assert updated.name == "Updated Name"
    mock_db.flush.assert_awaited()


# =====================================================================
# MemberRepository Tests
# =====================================================================

@pytest.mark.asyncio
async def test_member_repository_all_methods(mock_db):
    repo = MemberRepository(mock_db)
    cid = uuid.uuid4()
    uid = uuid.uuid4()
    mid = uuid.uuid4()

    dummy_member = ConversationMember(conversation_id=cid, user_id=uid, role=MemberRole.MEMBER.value)
    dummy_member.id = mid

    # 1. add_member
    member = await repo.add_member(cid, uid, MemberRole.ADMIN)
    assert member.role == MemberRole.ADMIN.value
    mock_db.add.assert_called_with(member)

    # 2. get_member
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = dummy_member
    mock_db.execute.return_value = mock_res
    res = await repo.get_member(cid, uid)
    assert res == dummy_member

    # 3. get_members
    mock_res.scalars.return_value.unique.return_value.all.return_value = [dummy_member]
    members = await repo.get_members(cid)
    assert members == [dummy_member]

    # 4. is_member
    repo.get_member = AsyncMock(side_effect=[dummy_member, None])
    assert await repo.is_member(cid, uid) is True
    assert await repo.is_member(cid, uid) is False

    # 5. is_admin_or_owner
    repo.get_member = AsyncMock(side_effect=[
        None,  # Not found -> False
        ConversationMember(role=MemberRole.MEMBER.value),  # Member -> False
        ConversationMember(role=MemberRole.ADMIN.value),   # Admin -> True
        ConversationMember(role=MemberRole.OWNER.value),   # Owner -> True
    ])
    assert await repo.is_admin_or_owner(cid, uid) is False
    assert await repo.is_admin_or_owner(cid, uid) is False
    assert await repo.is_admin_or_owner(cid, uid) is True
    assert await repo.is_admin_or_owner(cid, uid) is True

    # 6. remove_member
    repo.get_member = AsyncMock(side_effect=[None, dummy_member])
    assert await repo.remove_member(cid, uid) is False
    assert await repo.remove_member(cid, uid) is True
    mock_db.delete.assert_awaited_once_with(dummy_member)

    # 7. update_role
    repo.get_member = AsyncMock(side_effect=[None, dummy_member])
    assert await repo.update_role(cid, uid, MemberRole.ADMIN) is None
    updated = await repo.update_role(cid, uid, MemberRole.ADMIN)
    assert updated.role == MemberRole.ADMIN.value

    # 8. count_owners
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [dummy_member]
    mock_db.execute.return_value = mock_res
    assert await repo.count_owners(cid) == 1

    # 9. update_last_read
    msg_id = uuid.uuid4()
    repo.get_member = AsyncMock(side_effect=[None, dummy_member])
    assert await repo.update_last_read(cid, uid, msg_id) is None
    read_updated = await repo.update_last_read(cid, uid, msg_id)
    assert read_updated.last_read_message_id == msg_id


# =====================================================================
# MessageRepository Tests
# =====================================================================

@pytest.mark.asyncio
async def test_message_repository_all_methods(mock_db):
    repo = MessageRepository(mock_db)
    cid = uuid.uuid4()
    sender_id = uuid.uuid4()
    msg_id = uuid.uuid4()

    dummy_msg = Message(
        conversation_id=cid,
        sender_id=sender_id,
        content="Hello!",
        message_type=MessageType.TEXT.value,
    )
    dummy_msg.id = msg_id
    dummy_msg.created_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    # 1. create
    msg = await repo.create(cid, sender_id, "Hello!", MessageType.TEXT)
    assert msg.content == "Hello!"
    mock_db.add.assert_called_with(msg)
    mock_db.flush.assert_awaited()

    # 2. get_by_id
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = dummy_msg
    mock_db.execute.return_value = mock_res
    res = await repo.get_by_id(msg_id)
    assert res == dummy_msg

    # 3. list_by_conversation (no cursor, has_more=False)
    mock_res.scalars.return_value.unique.return_value.all.return_value = [dummy_msg]
    messages, next_cursor, has_more = await repo.list_by_conversation(cid, limit=2)
    assert len(messages) == 1
    assert next_cursor is None
    assert has_more is False

    # 4. list_by_conversation (has_more=True, cursor generated)
    msg2 = Message(conversation_id=cid, content="Second")
    msg2.id = uuid.uuid4()
    msg2.created_at = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)

    msg3 = Message(conversation_id=cid, content="Third")
    msg3.id = uuid.uuid4()
    msg3.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    # limit is 2, but we return 3 items to trigger has_more
    mock_res.scalars.return_value.unique.return_value.all.return_value = [dummy_msg, msg2, msg3]
    messages, next_cursor, has_more = await repo.list_by_conversation(cid, limit=2)
    assert len(messages) == 2
    assert has_more is True
    assert next_cursor == str(msg2.id)

    # 5. list_by_conversation with valid cursor ID
    cursor_anchor = Message(conversation_id=cid, created_at=datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc))
    repo.get_by_id = AsyncMock(return_value=cursor_anchor)
    mock_res.scalars.return_value.unique.return_value.all.return_value = [dummy_msg]
    messages, _, _ = await repo.list_by_conversation(cid, limit=10, cursor=str(msg_id))
    assert len(messages) == 1

    # 6. list_by_conversation with invalid / non-existent cursor
    repo.get_by_id = AsyncMock(return_value=None)
    mock_res.scalars.return_value.unique.return_value.all.return_value = [dummy_msg]
    messages, _, _ = await repo.list_by_conversation(cid, limit=10, cursor="not-a-valid-uuid")
    assert len(messages) == 1
