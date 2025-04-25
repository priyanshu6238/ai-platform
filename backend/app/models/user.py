from sqlmodel import Field, Relationship, SQLModel
from pydantic import EmailStr

# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: int = Field(default=None, primary_key=True)  # Changed to int from uuid.UUID
    hashed_password: str
    documents: list["Document"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    projects: list["ProjectUser"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    api_keys: list["APIKey"] = Relationship(back_populates="user")


class UserOrganization(UserBase):
    id: int  # Changed to int from uuid.UUID
    organization_id: int | None


class UserProjectOrg(UserOrganization):
    project_id: int


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: int  # Changed to int from uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
