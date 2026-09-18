import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    """Payload for creating a new conversation."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    member_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="User IDs to add as initial members (creator is added automatically)",
    )


class ConversationUpdate(BaseModel):
    """Payload for updating conversation metadata."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None


class ConversationResponse(BaseModel):
    """Public representation of a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ConversationListResponse(BaseModel):
    """Wrapper for listing multiple conversations."""

    conversations: list[ConversationResponse]
    count: int
