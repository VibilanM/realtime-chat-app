"""Conversation route handlers."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import get_current_user
from app.config.database import get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
)
from app.service.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
)
async def create_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conversation = await service.create_conversation(data, user)
    return conversation


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List conversations for the current user",
)
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conversations = await service.list_conversations(user)
    return ConversationListResponse(
        conversations=conversations,
        count=len(conversations),
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation details",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    return await service.get_conversation(conversation_id, user)


@router.put(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation metadata",
)
async def update_conversation(
    conversation_id: uuid.UUID,
    data: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    return await service.update_conversation(conversation_id, data, user)


@router.delete(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Soft-delete a conversation",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    return await service.delete_conversation(conversation_id, user)
