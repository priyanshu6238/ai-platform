from sqlmodel import Field, Relationship, SQLModel


# Shared properties for a Project
class ProjectBase(SQLModel):
    name: str = Field(index=True, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


# Properties to receive via API on creation
class ProjectCreate(ProjectBase):
    organization_id: int  # This will reference the Organization ID, assumed to be int


# Properties to receive via API on update, all are optional
class ProjectUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = Field(default=None)


# Database model for Project
class Project(ProjectBase, table=True):
    id: int = Field(default=None, primary_key=True)  # ID as int
    organization_id: int = Field(foreign_key="organization.id", index=True)  # Foreign Key to Organization, assumed int

    users: list["ProjectUser"] = Relationship(
        back_populates="project", cascade_delete=True  # Cascade delete for related ProjectUser entries
    )


# Properties to return via API
class ProjectPublic(ProjectBase):
    id: int  # ID of the project
    organization_id: int  # The associated organization ID


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]  # List of public projects
    count: int  # The total count of projects
