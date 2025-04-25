from uuid import UUID
from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now, generate_random_int
from .user import User


class Document(SQLModel, table=True):
    id: int = Field(
        default_factory=generate_random_int,  # Changed to int for integer ID
        primary_key=True,
    )
    owner_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    fname: str
    object_store_url: str
    created_at: datetime = Field(
        default_factory=now,
    )
    # updated_at: datetime | None
    deleted_at: datetime | None

    owner: User = Relationship(back_populates="documents")
