import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """Public representation of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime
