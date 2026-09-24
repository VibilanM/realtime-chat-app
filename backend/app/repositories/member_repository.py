"""Data access layer for conversation members."""

import uuid

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.constants.enums import MemberRole
from app.models.conversation_member import ConversationMember
from app.models.user import User


class MemberRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_member(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        role: MemberRole = MemberRole.MEMBER,
    ) -> ConversationMember:
        member = ConversationMember(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role.value,
        )
        self.db.add(member)
        await self.db.flush()
        return member

    async def get_member(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConversationMember | None:
        result = await self.db.execute(
            select(ConversationMember).where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_members(
        self, conversation_id: uuid.UUID
    ) -> list[ConversationMember]:
        result = await self.db.execute(
            select(ConversationMember)
            .options(
                joinedload(ConversationMember.user),
                joinedload(ConversationMember.last_read_message),
            )
            .where(ConversationMember.conversation_id == conversation_id)
            .order_by(ConversationMember.joined_at)
        )
        return list(result.scalars().unique().all())

    async def is_member(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        member = await self.get_member(conversation_id, user_id)
        return member is not None

    async def is_admin_or_owner(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        member = await self.get_member(conversation_id, user_id)
        if member is None:
            return False
        return member.role in (MemberRole.ADMIN.value, MemberRole.OWNER.value)

    async def remove_member(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        member = await self.get_member(conversation_id, user_id)
        if member is None:
            return False
        await self.db.delete(member)
        await self.db.flush()
        return True

    async def update_role(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        role: MemberRole,
    ) -> ConversationMember | None:
        member = await self.get_member(conversation_id, user_id)
        if member is None:
            return None
        member.role = role.value
        await self.db.flush()
        return member

    async def count_owners(self, conversation_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(ConversationMember).where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.role == MemberRole.OWNER.value,
                )
            )
        )
        return len(result.scalars().all())

    async def update_last_read(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> ConversationMember | None:
        """
        Update the member's last read message watermark and read timestamp.
        """
        member = await self.get_member(conversation_id, user_id)
        if member is None:
            return None

        member.last_read_message_id = message_id
        member.last_read_at = func.now()
        await self.db.flush()
        return member
