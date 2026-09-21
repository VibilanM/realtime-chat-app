import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models.user import User

VALID_USERNAMES = {"alice", "bob", "mark"}

DEV_USERS = [
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"},
    {"name": "Mark", "email": "mark@example.com"},
]


async def _ensure_dev_users_exist(db: AsyncSession) -> None:
    """Seed the three dev users if they don't exist yet."""
    for user_data in DEV_USERS:
        result = await db.execute(
            select(User).where(User.email == user_data["email"])
        )
        if result.scalar_one_or_none() is None:
            db.add(User(**user_data))
    await db.flush()


async def get_user_from_username(username_raw: str, db: AsyncSession) -> User:
    """
    Core authentication logic: validates username, ensures seeding,
    and returns the User ORM object.
    
    Can be called by both HTTP and WebSocket authentication layers.
    """
    username = username_raw.strip().lower()

    if username not in VALID_USERNAMES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unknown user '{username_raw}'. Valid users: alice, bob, mark",
        )

    # Ensure dev users are seeded
    await _ensure_dev_users_exist(db)

    # Look up by email (deterministic from username)
    email = f"{username}@example.com"
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dev user seeding failed",
        )

    return user


async def get_current_user(
    x_user_id: str = Header(..., description="Username of the requesting user (alice, bob, or mark)"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate the requesting user by matching the X-User-Id header."""
    return await get_user_from_username(x_user_id, db)