"""User route handlers (dev-mode user listing)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import get_current_user, _ensure_dev_users_exist
from app.config.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List all dev users",
)
async def list_users(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all seeded dev users. Requires authentication."""
    await _ensure_dev_users_exist(db)
    result = await db.execute(select(User).order_by(User.name))
    return list(result.scalars().all())
