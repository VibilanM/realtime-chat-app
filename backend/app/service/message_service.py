"""Business logic for messages."""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.redis import get_redis_client
from app.exceptions.exceptions import ForbiddenError, NotFoundError
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate

class MessageService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.member_repo = MemberRepository(db)
        self.conversation_repo = ConversationRepository(db)
        self.redis_client = get_redis_client()

    def calculate_read_by_all(
        self, members: list[ConversationMember]
    ) -> Message | None:
        """
        Calculates the highest message read by ALL members using the Min-Watermark algorithm.
        Returns the Message object of the minimum watermark across all members,
        or None if at least one member has not read any message.
        """
        if not members:
            return None

        # In a 1-person chat (e.g. self-chat / saved notes), read by all immediately
        if len(members) == 1:
            return members[0].last_read_message

        # In a multi-member chat, if any member has never read or sent any message,
        # then no message can have been read by all members.
        for m in members:
            if m.last_read_message is None:
                return None

        # The member whose last_read_message has the earliest created_at is the bottleneck.
        # All messages created on or before this member's watermark have been seen by everyone.
        slowest_member = min(members, key=lambda m: m.last_read_message.created_at)
        return slowest_member.last_read_message

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

        # Flush to get the created_at timestamp
        await self.db.flush()

        # Sender has created and therefore read their own message
        await self.member_repo.update_last_read(conversation_id, sender.id, message.id)

        await self.db.commit()

        # Determine if message is read by all (e.g. in a 1-member conversation)
        members = await self.member_repo.get_members(conversation_id)
        read_by_all_msg = self.calculate_read_by_all(members)
        is_read_by_all = (
            read_by_all_msg is not None
            and message.created_at is not None
            and message.created_at <= read_by_all_msg.created_at
        )

        event_payload = {
            "type": "message.created",
            "event": "message.created",
            "data": {
                "id": str(message.id),
                "conversation_id": str(message.conversation_id),
                "sender_id": str(sender.id),
                "sender_name": sender.name,
                "content": message.content,
                "message_type": message.message_type,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "is_read_by_all": is_read_by_all,
            },
        }

        channel_name = f"conversation:{str(conversation_id)}"
        await self.redis_client.publish(channel_name, json.dumps(event_payload))

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

    async def mark_as_read(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        user: User,
    ) -> dict | None:
        """
        Process a read receipt event:
        1. Validates user membership.
        2. Validates message exists and belongs to conversation.
        3. Prevents read pointer from moving backwards (monotonic check).
        4. Updates member's last_read_message_id and last_read_at in PostgreSQL.
        5. Computes conversation Min-Watermark (the highest message read by all members).
        6. Publishes `message.read` event to Redis with `read_by_all_message_id` and `is_read_by_all`.
        """
        # 1. Validate membership
        await self._validate_membership(conversation_id, user)

        # 2. Validate target message exists
        target_message = await self.message_repo.get_by_id(message_id)
        if target_message is None:
            return None

        # Verify message belongs to the stated conversation
        if target_message.conversation_id != conversation_id:
            return None

        # 3. Retrieve current membership record
        member = await self.member_repo.get_member(conversation_id, user.id)
        if member is None:
            return None

        # 4. Monotonic ordering check
        if member.last_read_message_id is not None:
            current_read_msg = await self.message_repo.get_by_id(member.last_read_message_id)
            if current_read_msg is not None:
                if target_message.created_at <= current_read_msg.created_at:
                    return None

        # 5. Update PostgreSQL
        await self.member_repo.update_last_read(conversation_id, user.id, message_id)
        await self.db.commit()

        # 6. Calculate Min-Watermark (read-by-all threshold)
        members = await self.member_repo.get_members(conversation_id)
        read_by_all_msg = self.calculate_read_by_all(members)
        read_by_all_message_id = str(read_by_all_msg.id) if read_by_all_msg else None

        is_target_read_by_all = (
            read_by_all_msg is not None
            and target_message.created_at <= read_by_all_msg.created_at
        )

        # 7. Publish real-time event to Redis
        read_payload = {
            "type": "message.read",
            "event": "message.read",
            "data": {
                "conversation_id": str(conversation_id),
                "user_id": str(user.id),
                "user_name": user.name.lower(),
                "message_id": str(message_id),
                "read_at": target_message.created_at.isoformat(),
                "read_by_all_message_id": read_by_all_message_id,
                "is_read_by_all": is_target_read_by_all,
            },
        }

        channel_name = f"conversation:{str(conversation_id)}"
        await self.redis_client.publish(channel_name, json.dumps(read_payload))

        return read_payload