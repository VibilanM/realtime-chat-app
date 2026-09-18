"""Business logic for messages."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import MessageType
from app.exceptions.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.message import Message
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate, MessageUpdate


class MessageService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.member_repo = MemberRepository(db)
        self.conversation_repo = ConversationRepository(db)

    async def _validate_membership(
        self, conversation_id: uuid.UUID, user: User
    ) -> None:
        """Verify the conversation exists and user is a member."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if not await self.member_repo.is_member(conversation_id, user.id):
            raise ForbiddenError("You are not a member of this conversation")

    async def send_message(
        self,
        conversation_id: uuid.UUID,
        data: MessageCreate,
        sender: User,
    ) -> Message:
        """Send a new message to a conversation."""
        await self._validate_membership(conversation_id, sender)

        # Validate reply target if provided
        if data.reply_to_message_id:
            reply_msg = await self.message_repo.get_by_id(data.reply_to_message_id)
            if reply_msg is None:
                raise NotFoundError("Reply target message", str(data.reply_to_message_id))
            if reply_msg.conversation_id != conversation_id:
                raise ValidationError("Reply target message is not in this conversation")

        message = await self.message_repo.create(
            conversation_id=conversation_id,
            sender_id=sender.id,
            content=data.content,
            message_type=data.message_type,
            reply_to_message_id=data.reply_to_message_id,
        )

        return message

    async def get_message(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        user: User,
    ) -> Message:
        """Fetch a specific message."""
        await self._validate_membership(conversation_id, user)

        message = await self.message_repo.get_by_id(message_id)
        if message is None:
            raise NotFoundError("Message", str(message_id))
        if message.conversation_id != conversation_id:
            raise NotFoundError("Message", str(message_id))

        return message

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        user: User,
        limit: int = 30,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None, bool]:
        """List messages with cursor-based pagination."""
        await self._validate_membership(conversation_id, user)

        return await self.message_repo.list_by_conversation(
            conversation_id=conversation_id,
            limit=limit,
            cursor=cursor,
        )

    async def edit_message(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        data: MessageUpdate,
        user: User,
    ) -> Message:
        """Edit a message (sender only)."""
        await self._validate_membership(conversation_id, user)

        message = await self.message_repo.get_by_id(message_id)
        if message is None:
            raise NotFoundError("Message", str(message_id))
        if message.conversation_id != conversation_id:
            raise NotFoundError("Message", str(message_id))

        # Only the sender can edit
        if message.sender_id != user.id:
            raise ForbiddenError("You can only edit your own messages")

        # Cannot edit deleted messages
        if message.deleted_at is not None:
            raise ValidationError("Cannot edit a deleted message")

        return await self.message_repo.update(message, data.content)

    async def delete_message(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        user: User,
    ) -> Message:
        """Soft-delete a message (sender or admin/owner)."""
        await self._validate_membership(conversation_id, user)

        message = await self.message_repo.get_by_id(message_id)
        if message is None:
            raise NotFoundError("Message", str(message_id))
        if message.conversation_id != conversation_id:
            raise NotFoundError("Message", str(message_id))

        # Sender can delete their own, admin/owner can delete any
        is_sender = message.sender_id == user.id
        is_admin = await self.member_repo.is_admin_or_owner(conversation_id, user.id)

        if not is_sender and not is_admin:
            raise ForbiddenError("You can only delete your own messages (or be an admin)")

        if message.deleted_at is not None:
            raise ValidationError("Message is already deleted")

        return await self.message_repo.soft_delete(message)

    async def search_messages(
        self,
        conversation_id: uuid.UUID,
        query: str,
        user: User,
        limit: int = 30,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None, bool]:
        """Search messages within a conversation."""
        await self._validate_membership(conversation_id, user)

        return await self.message_repo.search(
            conversation_id=conversation_id,
            query=query,
            limit=limit,
            cursor=cursor,
        )
