"""Member route handlers."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import get_current_user
from app.config.database import get_db
from app.models.user import User
from app.schemas.member import (
    MemberAdd,
    MemberListResponse,
    MemberResponse,
    MemberRoleUpdate,
)
from app.service.member_service import MemberService

router = APIRouter(
    prefix="/conversations/{conversation_id}/members",
    tags=["Members"],
)


def _member_to_response(member) -> MemberResponse:
    """Convert a ConversationMember ORM object to a response schema."""
    return MemberResponse(
        id=member.id,
        conversation_id=member.conversation_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
        user_name=member.user.name if member.user else None,
        user_email=member.user.email if member.user else None,
    )


@router.get(
    "",
    response_model=MemberListResponse,
    summary="List conversation members",
)
async def get_members(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MemberService(db)
    members = await service.get_members(conversation_id, user)
    member_responses = [_member_to_response(m) for m in members]
    return MemberListResponse(members=member_responses, count=len(member_responses))


@router.post(
    "",
    response_model=MemberListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add members to a conversation",
)
async def add_members(
    conversation_id: uuid.UUID,
    data: MemberAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MemberService(db)
    members = await service.add_members(conversation_id, data.user_ids, user)
    member_responses = [_member_to_response(m) for m in members]
    return MemberListResponse(members=member_responses, count=len(member_responses))


@router.put(
    "/{user_id}",
    response_model=MemberResponse,
    summary="Change a member's role",
)
async def update_member_role(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MemberRoleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MemberService(db)
    member = await service.update_role(conversation_id, user_id, data.role, user)
    return _member_to_response(member)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from a conversation",
)
async def remove_member(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MemberService(db)
    await service.remove_member(conversation_id, user_id, user)
