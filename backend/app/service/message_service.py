"""Business logic for messages."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.exceptions import ForbiddenError, NotFoundError
from app.models.message import Message
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate
from app.websocket.connection_manager import manager


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

        # Insert message into PostgreSQL
        message = await self.message_repo.create(
            conversation_id=conversation_id,
            sender_id=sender.id,
            content=data.content,
            message_type=data.message_type,
        )

        # Flush to get the created_at timestamp, then commit is handled by get_db
        await self.db.flush()

        # Broadcast to all WebSocket clients watching this conversation
        # This happens AFTER the database insert succeeds
        await manager.broadcast_to_conversation(
            str(conversation_id),
            {
                "event": "message.created",
                "data": {
                    "id": str(message.id),
                    "conversation_id": str(message.conversation_id),
                    "sender_id": str(message.sender_id),
                    "sender_name": sender.name,
                    "content": message.content,
                    "message_type": message.message_type,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                },
            },
        )

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
