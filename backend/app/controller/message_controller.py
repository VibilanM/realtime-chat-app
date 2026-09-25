"""Message route handlers."""

from __future__ import annotations

import uuid

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import get_current_user
from app.config.database import get_db
from app.models.user import User
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    PaginatedMessages,
)
from app.service.message_service import MessageService

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["Messages"],
)


def _message_to_response(
    message, read_by_all_created_at: datetime | None = None
) -> MessageResponse:
    """Convert a Message ORM object to a response schema, setting is_read_by_all."""
    is_read_by_all = (
        read_by_all_created_at is not None
        and message.created_at is not None
        and message.created_at <= read_by_all_created_at
    )
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        message_type=message.message_type,
        content=message.content,
        created_at=message.created_at,
        sender_name=message.sender.name if message.sender else None,
        is_read_by_all=is_read_by_all,
    )


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message to a conversation",
)
async def send_message(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)
    message = await service.send_message(conversation_id, data, user)

    members = await service.member_repo.get_members(conversation_id)
    read_by_all_msg = service.calculate_read_by_all(members)
    watermark_time = read_by_all_msg.created_at if read_by_all_msg else None

    return _message_to_response(message, watermark_time)


@router.get(
    "",
    response_model=PaginatedMessages,
    summary="List messages with cursor-based pagination",
)
async def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(30, ge=1, le=100),
    cursor: str | None = Query(None, description="Message ID cursor for pagination"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)
    members = await service.member_repo.get_members(conversation_id)
    read_by_all_msg = service.calculate_read_by_all(members)
    watermark_time = read_by_all_msg.created_at if read_by_all_msg else None

    messages, next_cursor, has_more = await service.list_messages(
        conversation_id, user, limit, cursor
    )
    return PaginatedMessages(
        messages=[_message_to_response(m, watermark_time) for m in messages],
        next_cursor=next_cursor,
        has_more=has_more,
    )
