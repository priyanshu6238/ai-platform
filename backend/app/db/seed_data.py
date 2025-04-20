import uuid
from sqlmodel import Session
from app.models import Organization, Project, User, APIKey
from app.core.security import get_password_hash, encrypt_api_key
import secrets


def create_organization(session: Session, org_data: dict) -> Organization:
    """Create an organization from data."""
    organization = Organization(**org_data)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


def create_project(session: Session, project_data: dict, organization_id: int) -> Project:
    """Create a project from data."""
    project = Project(**project_data, organization_id=organization_id)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def create_user(session: Session, user_data: dict) -> User:
    """Create a user from data."""
    hashed_password = get_password_hash(user_data.pop('password'))
    user = User(**user_data, hashed_password=hashed_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_api_key(session: Session, user: User, organization: Organization) -> APIKey:
    """Create an API key for user and organization."""
    token = secrets.token_urlsafe(32)
    raw_key = "ApiKey " + token
    encrypted_key = encrypt_api_key(raw_key)

    api_key = APIKey(
        user_id=user.id,
        organization_id=organization.id,
        key=encrypted_key,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key


def seed_database(session: Session) -> None:
    """Seed the database with initial data."""
    try:
        # Check if database is already seeded
        existing_orgs = session.query(Organization).count()
        if existing_orgs > 0:
            return
            
        # Create organization
        organization = create_organization(session, {
            "name": "Project Tech4dev",
            "description": "Default organization for development",
            "is_active": True
        })
        
        # Create projects
        projects = [
            {
                "name": "Glific",
                "description": "Two way communication platform",
                "is_active": True
            },
            {
                "name": "Dalgo",
                "description": "Data platform for the social sector",
                "is_active": True
            }
        ]
        
        for project_data in projects:
            create_project(session, project_data, organization.id)
        
        # Create users and their API keys
        users = [
            {
                "email": "superuser@example.com",
                "password": "superuser123",
                "full_name": "SUPERUSER",
                "is_superuser": True,
                "is_active": True
            },
            {
                "email": "admin@example.com",
                "password": "admin123",
                "full_name": "ADMIN",
                "is_superuser": False,
                "is_active": True
            }
        ]
        
        for user_data in users:
            user = create_user(session, user_data)
            create_api_key(session, user, organization)
        
        # Verify data was created
        org_count = session.query(Organization).count()
        project_count = session.query(Project).count()
        user_count = session.query(User).count()
        api_key_count = session.query(APIKey).count()
        
    except Exception as e:
        session.rollback()
        raise


def clear_database(session: Session) -> None:
    """Clear all seeded data from the database."""
    session.query(APIKey).delete()
    session.query(Project).delete()
    session.query(Organization).delete()
    session.query(User).delete()
    session.commit()


if __name__ == "__main__":
    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        clear_database(session)
        seed_database(session)
    except Exception as e:
        session.rollback()
    finally:
        session.close() 