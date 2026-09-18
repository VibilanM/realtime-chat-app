"""Data access layer for messages."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.constants.enums import MessageType
from app.models.message import Message


class MessageRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        conversation_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        reply_to_message_id: uuid.UUID | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type.value,
            reply_to_message_id=reply_to_message_id,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def get_by_id(self, message_id: uuid.UUID) -> Message | None:
        result = await self.db.execute(
            select(Message)
            .options(joinedload(Message.sender))
            .where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int = 30,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None, bool]:
        """
        Fetch messages for a conversation using cursor-based pagination.

        Cursor is a message ID. Messages are returned newest-first.
        Returns (messages, next_cursor, has_more).
        """
        query = (
            select(Message)
            .options(joinedload(Message.sender))
            .where(
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.desc())
        )

        # Apply cursor — fetch messages older than the cursor message
        if cursor:
            try:
                cursor_id = uuid.UUID(cursor)
            except ValueError:
                cursor_id = None

            if cursor_id:
                cursor_msg = await self.get_by_id(cursor_id)
                if cursor_msg:
                    query = query.where(Message.created_at < cursor_msg.created_at)

        # Fetch limit + 1 to check if there are more
        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        messages = list(result.scalars().unique().all())

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        next_cursor = str(messages[-1].id) if messages and has_more else None

        return messages, next_cursor, has_more

    async def update(self, message: Message, content: str) -> Message:
        message.content = content
        message.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return message

    async def soft_delete(self, message: Message) -> Message:
        message.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return message

    async def search(
        self,
        conversation_id: uuid.UUID,
        query: str,
        limit: int = 30,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None, bool]:
        """
        Search messages in a conversation using ILIKE (MVP).
        Cursor pagination applied on search results.
        """
        stmt = (
            select(Message)
            .options(joinedload(Message.sender))
            .where(
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
                Message.content.ilike(f"%{query}%"),
            )
            .order_by(Message.created_at.desc())
        )

        if cursor:
            try:
                cursor_id = uuid.UUID(cursor)
            except ValueError:
                cursor_id = None

            if cursor_id:
                cursor_msg = await self.get_by_id(cursor_id)
                if cursor_msg:
                    stmt = stmt.where(Message.created_at < cursor_msg.created_at)

        stmt = stmt.limit(limit + 1)
        result = await self.db.execute(stmt)
        messages = list(result.scalars().unique().all())

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        next_cursor = str(messages[-1].id) if messages and has_more else None

        return messages, next_cursor, has_more
