"""Business logic for conversations."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import MemberRole
from app.exceptions.exceptions import ForbiddenError, NotFoundError
from app.models.conversation import Conversation
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.user_repository import UserRepository
from app.schemas.conversation import ConversationCreate, ConversationUpdate


class ConversationService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.member_repo = MemberRepository(db)
        self.user_repo = UserRepository(db)

    async def create_conversation(
        self, data: ConversationCreate, creator: User
    ) -> Conversation:
        """
        Create a conversation, add the creator as owner,
        and add any initial members.
        """
        conversation = await self.conversation_repo.create(
            name=data.name,
            description=data.description,
            created_by=creator.id,
        )

        # Add creator as owner
        await self.member_repo.add_member(
            conversation_id=conversation.id,
            user_id=creator.id,
            role=MemberRole.OWNER,
        )

        # Add initial members
        if data.member_ids:
            # Validate that all member IDs are real users
            users = await self.user_repo.get_by_ids(data.member_ids)
            found_ids = {u.id for u in users}
            for member_id in data.member_ids:
                if member_id not in found_ids:
                    raise NotFoundError("User", str(member_id))
                if member_id != creator.id:
                    await self.member_repo.add_member(
                        conversation_id=conversation.id,
                        user_id=member_id,
                        role=MemberRole.MEMBER,
                    )

        return conversation

    async def get_conversation(
        self, conversation_id: uuid.UUID, user: User
    ) -> Conversation:
        """Get a conversation, verifying the user is a member."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if not await self.member_repo.is_member(conversation_id, user.id):
            raise ForbiddenError("You are not a member of this conversation")

        return conversation

    async def list_conversations(self, user: User) -> list[Conversation]:
        """List all active conversations the user belongs to."""
        return await self.conversation_repo.list_by_user(user.id)

    async def update_conversation(
        self,
        conversation_id: uuid.UUID,
        data: ConversationUpdate,
        user: User,
    ) -> Conversation:
        """Update conversation metadata (admin/owner only)."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if not await self.member_repo.is_admin_or_owner(conversation_id, user.id):
            raise ForbiddenError("Only admins and owners can update conversations")

        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            conversation = await self.conversation_repo.update(
                conversation, **update_data
            )

        return conversation

    async def delete_conversation(
        self, conversation_id: uuid.UUID, user: User
    ) -> Conversation:
        """Soft-delete a conversation (admin/owner only)."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if not await self.member_repo.is_admin_or_owner(conversation_id, user.id):
            raise ForbiddenError("Only admins and owners can delete conversations")

        return await self.conversation_repo.soft_delete(conversation)
