"""Data access layer for conversations."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember


class ConversationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        created_by: uuid.UUID,
        description: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            name=name,
            description=description,
            created_by=created_by,
        )
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        """Return all active conversations the user is a member of."""
        result = await self.db.execute(
            select(Conversation)
            .join(ConversationMember)
            .where(
                ConversationMember.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        conversation: Conversation,
        **kwargs,
    ) -> Conversation:
        for key, value in kwargs.items():
            if hasattr(conversation, key) and value is not None:
                setattr(conversation, key, value)
        await self.db.flush()
        return conversation

    async def soft_delete(self, conversation: Conversation) -> Conversation:
        from datetime import datetime, timezone

        conversation.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return conversation
