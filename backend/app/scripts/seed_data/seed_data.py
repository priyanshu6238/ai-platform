import uuid
import json
from pathlib import Path
from sqlmodel import Session, select, delete
from app.models import Organization, Project, User, APIKey
from app.core.security import get_password_hash, encrypt_api_key
from app.core.db import engine
import logging
from datetime import datetime


def load_seed_data() -> dict:
    """Load seed data from JSON file."""
    json_path = Path(__file__).parent / "seed_data.json"
    try:
        with open(json_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: Seed data file not found at {json_path}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error: Failed to decode JSON from {json_path}: {e}")
        raise


def create_organization(session: Session, org_data: dict) -> Organization:
    """Create an organization from data."""
    print(f"Creating organization: {org_data['name']}")
    organization = Organization(
        id=org_data["id"], name=org_data["name"], is_active=org_data["is_active"]
    )
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


def create_project(session: Session, project_data: dict) -> Project:
    """Create a project from data."""
    print(f"Creating project: {project_data['name']}")
    project = Project(
        id=project_data["id"],
        name=project_data["name"],
        description=project_data["description"],
        is_active=project_data["is_active"],
        organization_id=project_data["organization_id"],
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def create_user(session: Session, user_data: dict) -> User:
    """Create a user from data."""
    print(f"Creating user: {user_data['email']}")
    password = user_data["password"]
    hashed_password = get_password_hash(password)
    user = User(
        id=uuid.UUID(user_data["id"]),
        email=user_data["email"],
        full_name=user_data["full_name"],
        is_superuser=user_data["is_superuser"],
        is_active=user_data["is_active"],
        hashed_password=hashed_password,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_api_key(session: Session, api_key_data: dict) -> APIKey:
    """Create an API key from data."""
    print(f"Creating API key for user {api_key_data['user_id']}")
    encrypted_api_key = encrypt_api_key(api_key_data["api_key"])
    api_key = APIKey(
        id=api_key_data["id"],
        organization_id=api_key_data["organization_id"],
        user_id=uuid.UUID(api_key_data["user_id"]),
        key=encrypted_api_key,
        is_deleted=api_key_data["is_deleted"],
        deleted_at=api_key_data["deleted_at"],
    )
    if "created_at" in api_key_data:
        api_key.created_at = datetime.fromisoformat(
            api_key_data["created_at"].replace("Z", "+00:00")
        )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key


def clear_database(session: Session) -> None:
    """Clear all seeded data from the database."""
    print("Clearing existing data...")
    session.exec(delete(APIKey))
    session.exec(delete(Project))
    session.exec(delete(Organization))
    session.exec(delete(User))
    session.commit()
    print("Existing data cleared.")


def seed_database(session: Session) -> None:
    """Seed the database with initial data."""
    print("Starting database seeding...")

    try:
        # Clear existing data first
        clear_database(session)

        # Load seed data from JSON
        seed_data = load_seed_data()

        # Create organizations first
        for org_data in seed_data["organization"]:
            organization = create_organization(session, org_data)
            print(f"Created organization: {organization.name} (ID: {organization.id})")

        # Create users next
        for user_data in seed_data["users"]:
            user = create_user(session, user_data)
            print(f"Created user: {user.email} (ID: {user.id})")

        # Create projects
        for project_data in seed_data["projects"]:
            project = create_project(session, project_data)
            print(f"Created project: {project.name} (ID: {project.id})")

        # Create API keys
        for api_key_data in seed_data["apikeys"]:
            api_key = create_api_key(session, api_key_data)
            print(f"Created API key (ID: {api_key.id})")

        print("Database seeding completed successfully!")
    except Exception as e:
        print(f"Error during seeding: {e}")
        session.rollback()
        raise


if __name__ == "__main__":
    print("Initializing database session...")
    with Session(engine) as session:
        try:
            seed_database(session)
            print("Database seeded successfully!")
        except Exception as e:
            print(f"Error seeding database: {e}")
            session.rollback()
