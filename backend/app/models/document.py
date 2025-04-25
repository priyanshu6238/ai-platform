from datetime import datetime
import uuid

from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now
from .user import User


class Document(SQLModel, table=True):
    id: int = Field(
        default_factory=lambda: int(uuid.uuid4().int % 1e6),  # Generate random integer
        primary_key=True,
    )
    owner_id: int = Field(
        foreign_key="user.id",
        nullable=False,
    )
    fname: str
    object_store_url: str
    created_at: datetime = Field(
        default_factory=now,
    )
    deleted_at: datetime | None

    owner: User = Relationship(back_populates="documents")
