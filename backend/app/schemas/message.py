import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import MessageType


class MessageCreate(BaseModel):
    """Payload for sending a new message."""

    content: str = Field(..., min_length=1)
    message_type: MessageType = MessageType.TEXT
    reply_to_message_id: uuid.UUID | None = None


class MessageUpdate(BaseModel):
    """Payload for editing a message."""

    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    """Public representation of a message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    message_type: str
    content: str | None = None
    reply_to_message_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    sender_name: str | None = None


class PaginatedMessages(BaseModel):
    """Cursor-paginated message list."""

    messages: list[MessageResponse]
    next_cursor: str | None = None
    has_more: bool = False


class MessageSearchParams(BaseModel):
    """Query parameters for message search."""

    q: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(30, ge=1, le=100)
    cursor: str | None = None
