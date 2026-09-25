from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import MessageType


class MessageCreate(BaseModel):
    """Payload for sending a new message."""

    content: str = Field(..., min_length=1)
    message_type: MessageType = MessageType.TEXT


class MessageResponse(BaseModel):
    """Public representation of a message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    message_type: str
    content: str | None = None
    created_at: datetime
    sender_name: str | None = None
    is_read_by_all: bool = False


class PaginatedMessages(BaseModel):
    """Cursor-paginated message list."""

    messages: list[MessageResponse]
    next_cursor: str | None = None
    has_more: bool = False
