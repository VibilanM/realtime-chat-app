"""Business logic for conversation members."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import MemberRole
from app.exceptions.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.conversation_member import ConversationMember
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.user_repository import UserRepository


class MemberService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.member_repo = MemberRepository(db)
        self.user_repo = UserRepository(db)

    async def _validate_conversation_and_admin(
        self, conversation_id: uuid.UUID, user: User
    ) -> None:
        """Verify conversation exists and user has admin/owner permission."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if not await self.member_repo.is_admin_or_owner(conversation_id, user.id):
            raise ForbiddenError("Only admins and owners can manage members")

    async def get_members(
        self, conversation_id: uuid.UUID, user: User
    ) -> list[ConversationMember]:
        """Get all members of a conversation."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if not await self.member_repo.is_member(conversation_id, user.id):
            raise ForbiddenError("You are not a member of this conversation")

        return await self.member_repo.get_members(conversation_id)

    async def add_members(
        self,
        conversation_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        user: User,
    ) -> list[ConversationMember]:
        """Add one or more members to a conversation (admin/owner only)."""
        await self._validate_conversation_and_admin(conversation_id, user)

        # Validate target users exist
        users = await self.user_repo.get_by_ids(user_ids)
        found_ids = {u.id for u in users}

        added = []
        for uid in user_ids:
            if uid not in found_ids:
                raise NotFoundError("User", str(uid))

            # Check if already a member
            if await self.member_repo.is_member(conversation_id, uid):
                raise ConflictError(f"User '{uid}' is already a member")

            member = await self.member_repo.add_member(
                conversation_id=conversation_id,
                user_id=uid,
                role=MemberRole.MEMBER,
            )
            added.append(member)

        return added

    async def remove_member(
        self,
        conversation_id: uuid.UUID,
        target_user_id: uuid.UUID,
        user: User,
    ) -> None:
        """Remove a member from a conversation (admin/owner only)."""
        await self._validate_conversation_and_admin(conversation_id, user)

        target_member = await self.member_repo.get_member(
            conversation_id, target_user_id
        )
        if target_member is None:
            raise NotFoundError("Member", str(target_user_id))

        # Prevent removing the last owner
        if target_member.role == MemberRole.OWNER.value:
            owner_count = await self.member_repo.count_owners(conversation_id)
            if owner_count <= 1:
                raise ForbiddenError("Cannot remove the last owner of a conversation")

        await self.member_repo.remove_member(conversation_id, target_user_id)

    async def update_role(
        self,
        conversation_id: uuid.UUID,
        target_user_id: uuid.UUID,
        role: MemberRole,
        user: User,
    ) -> ConversationMember:
        """Change a member's role (admin/owner only)."""
        await self._validate_conversation_and_admin(conversation_id, user)

        member = await self.member_repo.update_role(
            conversation_id, target_user_id, role
        )
        if member is None:
            raise NotFoundError("Member", str(target_user_id))

        return member
