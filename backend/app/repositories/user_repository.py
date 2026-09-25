"""Data access layer for users."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_ids(self, user_ids: list[uuid.UUID]) -> list[User]:
        result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
        return list(result.scalars().all())

    async def create(self, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self.db.add(user)
        await self.db.flush()
        return user
