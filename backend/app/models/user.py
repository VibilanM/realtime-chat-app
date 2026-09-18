from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    conversations_created = relationship(
        "Conversation", back_populates="creator", lazy="selectin"
    )
    memberships = relationship(
        "ConversationMember", back_populates="user", lazy="selectin"
    )
    messages_sent = relationship("Message", back_populates="sender", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.name} ({self.email})>"
