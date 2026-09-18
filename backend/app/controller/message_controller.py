"""Message route handlers."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import get_current_user
from app.config.database import get_db
from app.models.user import User
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageUpdate,
    PaginatedMessages,
)
from app.service.message_service import MessageService

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["Messages"],
)


def _message_to_response(message) -> MessageResponse:
    """Convert a Message ORM object to a response schema."""
    # If the message is soft-deleted, mask the content
    content = message.content
    if message.deleted_at is not None:
        content = "This message was deleted"

    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        message_type=message.message_type,
        content=content,
        reply_to_message_id=message.reply_to_message_id,
        created_at=message.created_at,
        updated_at=message.updated_at,
        deleted_at=message.deleted_at,
        sender_name=message.sender.name if message.sender else None,
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
    return _message_to_response(message)


@router.get(
    "/search",
    response_model=PaginatedMessages,
    summary="Search messages in a conversation",
)
async def search_messages(
    conversation_id: uuid.UUID,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(30, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)
    messages, next_cursor, has_more = await service.search_messages(
        conversation_id, q, user, limit, cursor
    )
    return PaginatedMessages(
        messages=[_message_to_response(m) for m in messages],
        next_cursor=next_cursor,
        has_more=has_more,
    )


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
    messages, next_cursor, has_more = await service.list_messages(
        conversation_id, user, limit, cursor
    )
    return PaginatedMessages(
        messages=[_message_to_response(m) for m in messages],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Get a specific message",
)
async def get_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)
    message = await service.get_message(conversation_id, message_id, user)
    return _message_to_response(message)


@router.put(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Edit a message",
)
async def edit_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    data: MessageUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)
    message = await service.edit_message(conversation_id, message_id, data, user)
    return _message_to_response(message)


@router.delete(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Soft-delete a message",
)
async def delete_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)
    message = await service.delete_message(conversation_id, message_id, user)
    return _message_to_response(message)
