from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel
from app.core.util import now
from .user import User


class Document(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)  # Changed from UUID to int
    owner_id: int = Field(                          # Changed from UUID to int
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    fname: str
    object_store_url: str
    created_at: datetime = Field(default_factory=now)
    deleted_at: datetime | None

    owner: User = Relationship(back_populates="documents")
