"""Seed organization table

Revision ID: 77dc462dc6b0
Revises: 0f205e3779ee
Create Date: 2024-04-11 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.core.security import get_password_hash
from app.models.user import User
from app.core.config import settings


# revision identifiers, used by Alembic.
revision = "77dc462dc6b0"
down_revision = "0f205e3779ee"
branch_labels = None
depends_on = None


def delete_all_data(session: Session) -> None:
    """Delete all data from the database."""
    session.query(Organization).delete()
    session.query(User).delete()
    session.commit()


def upgrade():
    # Create a session using the Alembic context
    session = Session(bind=op.get_bind())
    
    # Setup password hashing context
    password = settings.FIRST_SUPERUSER_PASSWORD
    hashed_password = get_password_hash(password)

    # Create default organization
    default_org = Organization(
        id=1,  # Explicitly set the ID
        name="Default Organization",
        description="Default organization for the system",
        is_active=True,
    )
    session.add(default_org)
    session.flush()  # Flush to get the organization ID

    # Create superuser
    superuser = User(
        id=1,  # Explicitly set the ID
        email=settings.FIRST_SUPERUSER,
        hashed_password=hashed_password,
        is_superuser=True,
        is_active=True,
        organization_id=default_org.id,
    )
    session.add(superuser)
    session.commit()


def downgrade():
    # Create a session using the Alembic context
    session = Session(bind=op.get_bind())
    
    # Delete all data
    delete_all_data(session)
