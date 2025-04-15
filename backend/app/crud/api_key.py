import uuid
import secrets
from datetime import datetime
from sqlmodel import Session, select
from app.core.security import verify_password, get_password_hash

from app.models.api_key import APIKey, APIKeyPublic, APIKeyCreateResponse


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash."""
    raw_key = "ApiKey " + secrets.token_urlsafe(32)
    hashed_key = get_password_hash(raw_key)
    return raw_key, hashed_key


# Create API Key
def create_api_key(
    session: Session, organization_id: uuid.UUID, user_id: uuid.UUID
) -> APIKeyCreateResponse:
    """
    Generates a new API key for an organization and associates it with a user.
    Returns the raw key (shown only once) and other key details.
    """
    # Generate raw key and its hash
    raw_key, hashed_key = generate_api_key()

    # Create API key record with hashed key
    api_key = APIKey(
        key=hashed_key,
        organization_id=organization_id,
        user_id=user_id,
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    # Return response with raw key and other details
    return APIKeyCreateResponse(
        key=raw_key,
        organization_id=api_key.organization_id,
        user_id=api_key.user_id,
        id=api_key.id,
        created_at=api_key.created_at,
    )


# Get API Key by ID
def get_api_key(session: Session, api_key_id: int) -> APIKeyPublic | None:
    """
    Retrieves an API key by its ID if it exists and is not deleted.
    """
    api_key = session.exec(
        select(APIKey).where(APIKey.id == api_key_id, APIKey.is_deleted == False)
    ).first()

    return APIKeyPublic.model_validate(api_key) if api_key else None


# Get API Keys for an Organization
def get_api_keys_by_organization(
    session: Session, organization_id: uuid.UUID
) -> list[APIKeyPublic]:
    """
    Retrieves all active API keys associated with an organization.
    """
    api_keys = session.exec(
        select(APIKey).where(
            APIKey.organization_id == organization_id, APIKey.is_deleted == False
        )
    ).all()

    return [APIKeyPublic.model_validate(api_key) for api_key in api_keys]


# Soft Delete (Revoke) API Key
def delete_api_key(session: Session, api_key_id: int) -> None:
    """
    Soft deletes (revokes) an API key by marking it as deleted.
    """
    api_key = session.get(APIKey, api_key_id)

    if not api_key or api_key.is_deleted:
        raise ValueError("API key not found or already deleted")

    api_key.is_deleted = True
    api_key.deleted_at = datetime.utcnow()

    session.add(api_key)
    session.commit()


def get_api_key_by_value(session: Session, api_key_value: str) -> APIKey | None:
    """
    Retrieve an API Key record by verifying the provided key against stored hashes.
    """
    # Get all active API keys
    api_keys = session.exec(select(APIKey).where(APIKey.is_deleted == False)).all()

    # Check each key
    for api_key in api_keys:
        if verify_password(api_key_value, api_key.key):
            return api_key

    return None


def get_api_key_by_user_org(
    session: Session, organization_id: int, user_id: str
) -> APIKey | None:
    """
    Retrieve an API key for a specific user and organization.
    """
    statement = select(APIKey).where(
        APIKey.organization_id == organization_id,
        APIKey.user_id == user_id,
        APIKey.is_deleted == False,
    )
    return session.exec(statement).first()
