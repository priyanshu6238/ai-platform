import uuid
import json
from pathlib import Path
from sqlmodel import Session
from app.models import Organization, Project, User, APIKey
from app.core.security import (
    get_password_hash,
    create_access_token,
)  # Import create_access_token
import secrets
from datetime import timedelta  # Import timedelta for token expiration


import logging # Or use print for simple scripts

def load_seed_data() -> dict:
    """Load seed data from JSON file."""
    json_path = Path(__file__).parent / "seed_data.json"
    try:
        with open(json_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: Seed data file not found at {json_path}")
        raise # Or return None/empty dict and handle in caller
    except json.JSONDecodeError as e:
        logging.error(f"Error: Failed to decode JSON from {json_path}: {e}")
        raise # Or return None/empty dict


def create_organization(session: Session, org_data: dict) -> Organization:
    """Create an organization from data."""
    print(f"Creating organization: {org_data['name']}")
    organization = Organization(**org_data)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


def create_project(
    session: Session, project_data: dict, organization_id: int
) -> Project:
    """Create a project from data."""
    print(
        f"Creating project: {project_data['name']} for organization {organization_id}"
    )
    project = Project(**project_data, organization_id=organization_id)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def create_user(session: Session, user_data: dict) -> User:
    """Create a user from data."""
    print(f"Creating user: {user_data['email']}")
    hashed_password = get_password_hash(user_data.pop("password"))
    user = User(**user_data, hashed_password=hashed_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_api_key(session: Session, user: User, organization: Organization) -> APIKey:
    """Create an API key for user and organization."""
    print(f"Creating API key for user {user.email} in organization {organization.name}")
    token = secrets.token_urlsafe(32)
    raw_key = "ApiKey " + token

    api_key = APIKey(
        user_id=user.id,
        organization_id=organization.id,
        key=raw_key, 
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key


def seed_database(session: Session) -> None:
    """Seed the database with initial data."""
    print("Starting database seeding...")

    try:
        # Check if database is already seeded
        existing_orgs = session.query(Organization).count()
        if existing_orgs > 0:
            print("Database already contains data. Skipping seeding.")
            return

        # Load seed data from JSON
        seed_data = load_seed_data()

        # Create organization
        organization = create_organization(session, seed_data["organization"])
        print(f"Created organization: {organization.name} (ID: {organization.id})")

        # Create projects
        for project_data in seed_data["projects"]:
            project = create_project(session, project_data, organization.id)
            print(f"Created project: {project.name} (ID: {project.id})")

        # Create users and their API keys
        for user_data in seed_data["users"]:
            user = create_user(session, user_data)
            print(f"Created user: {user.email} (ID: {user.id})")
            api_key = create_api_key(session, user, organization)
            print(f"Created API key for user {user.email}")

        # Verify data was created
        org_count = session.query(Organization).count()
        project_count = session.query(Project).count()
        user_count = session.query(User).count()
        api_key_count = session.query(APIKey).count()

        print("\nSeeding verification:")
        print(f"Organizations created: {org_count}")
        print(f"Projects created: {project_count}")
        print(f"Users created: {user_count}")
        print(f"API keys created: {api_key_count}")

        print("Database seeding completed successfully!")
    except Exception as e:
        print(f"Error during seeding: {e}")
        session.rollback()
        raise


def clear_database(session: Session) -> None:
    """Clear all seeded data from the database."""
    print("Clearing existing data...")
    session.query(APIKey).delete()
    session.query(Project).delete()
    session.query(Organization).delete()
    session.query(User).delete()
    session.commit()
    print("Existing data cleared.")


if __name__ == "__main__":
    from app.db.session import SessionLocal

    print("Initializing database session...")
    session = SessionLocal()
    try:
        clear_database(session)
        seed_database(session)
        print("Database seeded successfully!")
    except Exception as e:
        print(f"Error seeding database: {e}")
        session.rollback()
    finally:
        session.close()
