"""Test suite for SQLAlchemy models, representations, and enums."""

import uuid
from app.constants.enums import MemberRole, MessageType
from app.models.base import Base
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.message_read import MessageRead
from app.models.user import User


def test_models_repr_and_enums():
    """Test model string representations and enum values."""
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    mid = uuid.uuid4()

    # User
    user = User(name="Alice", email="alice@example.com")
    user.id = uid
    assert repr(user) == f"<User Alice (alice@example.com)>"

    # Conversation
    conv = Conversation(name="General", created_by=uid)
    conv.id = cid
    assert repr(conv) == f"<Conversation General ({cid})>"

    # ConversationMember
    member = ConversationMember(conversation_id=cid, user_id=uid, role=MemberRole.ADMIN.value)
    assert repr(member) == f"<ConversationMember user={uid} conv={cid} role=admin>"

    # Message
    message = Message(conversation_id=cid, sender_id=uid, message_type=MessageType.TEXT.value)
    message.id = mid
    assert repr(message) == f"<Message {mid} type=text>"

    # MessageAttachment
    attachment = MessageAttachment(
        message_id=mid,
        blob_url="http://blob/file.png",
        blob_name="file.png",
        content_type="image/png",
        file_size=1024,
    )
    assert repr(attachment) == "<MessageAttachment file.png (image/png)>"

    # MessageRead
    read_rec = MessageRead(message_id=mid, user_id=uid)
    assert repr(read_rec) == f"<MessageRead msg={mid} user={uid}>"

    # Enums
    assert MemberRole.OWNER.value == "owner"
    assert MemberRole.ADMIN.value == "admin"
    assert MemberRole.MEMBER.value == "member"

    assert MessageType.TEXT.value == "text"
    assert MessageType.IMAGE.value == "image"
    assert MessageType.VIDEO.value == "video"
    assert MessageType.FILE.value == "file"
    assert MessageType.TASK.value == "task"
