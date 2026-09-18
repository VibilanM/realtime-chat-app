import enum


class MemberRole(str, enum.Enum):
    """Roles a user can hold within a conversation."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MessageType(str, enum.Enum):
    """The kind of content a message carries."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"
    TASK = "task"
