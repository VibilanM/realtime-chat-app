from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import MemberRole


class MemberAdd(BaseModel):
    """Payload for adding members to a conversation."""

    user_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="User IDs to add"
    )


class MemberRoleUpdate(BaseModel):
    """Payload for changing a member's role."""

    role: MemberRole


class MemberResponse(BaseModel):
    """Public representation of a conversation member."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    user_name: str | None = None
    user_email: str | None = None

    # Added read watermark fields:
    last_read_message_id: uuid.UUID | None = None
    last_read_at: datetime | None = None


class MemberListResponse(BaseModel):
    """Wrapper for listing conversation members."""

    members: list[MemberResponse]
    count: int