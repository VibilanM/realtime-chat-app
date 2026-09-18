import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class MessageAttachment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "message_attachments"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False
    )
    blob_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    blob_name: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="attachments")

    def __repr__(self) -> str:
        return f"<MessageAttachment {self.blob_name} ({self.content_type})>"
