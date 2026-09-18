from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    conversations_created = relationship(
        "Conversation", back_populates="creator", lazy="noload"
    )
    memberships = relationship(
        "ConversationMember", back_populates="user", lazy="noload"
    )
    messages_sent = relationship("Message", back_populates="sender", lazy="noload")

    def __repr__(self) -> str:
        return f"<User {self.name} ({self.email})>"
