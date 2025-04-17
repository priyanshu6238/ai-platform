import uuid
import secrets
from datetime import datetime
from sqlmodel import Session, select
from app.core.security import verify_password, get_password_hash, encrypt_api_key, decrypt_api_key
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.core import settings

from app.models.api_key import APIKey, APIKeyPublic


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash."""
    raw_key = "ApiKey " + secrets.token_urlsafe(32)
    hashed_key = get_password_hash(raw_key)
    return raw_key, hashed_key


def create_api_key(
    session: Session, organization_id: uuid.UUID, user_id: uuid.UUID
) -> APIKeyPublic:
    """
    Generates a new API key for an organization and associates it with a user.
    Returns the API key details with the raw key (shown only once).
    """
    # Generate raw key and its hash
    raw_key = "ApiKey " + secrets.token_urlsafe(32)
    hashed_key = get_password_hash(raw_key)
    encrypted_key = encrypt_api_key(hashed_key)

    # Create API key record with encrypted hashed key
    api_key = APIKey(
        key=encrypted_key,  # Store the encrypted hashed key
        organization_id=organization_id,
        user_id=user_id,
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    # Set the raw key in the response (shown only once)
    api_key_dict = api_key.model_dump()
    api_key_dict["key"] = raw_key  # Return the raw key to the user

    return APIKeyPublic.model_validate(api_key_dict)


def get_api_key(session: Session, api_key_id: int) -> APIKeyPublic | None:
    """
    Retrieves an API key by its ID if it exists and is not deleted.
    """
    api_key = session.exec(
        select(APIKey).where(APIKey.id == api_key_id, APIKey.is_deleted == False)
    ).first()

    if api_key:
        # Return the API key without decrypting (we don't want to expose the hashed key)
        return APIKeyPublic.model_validate(api_key)
    return None


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

    # Return the API keys without decrypting (we don't want to expose the hashed keys)
    return [APIKeyPublic.model_validate(api_key) for api_key in api_keys]


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
        # Decrypt the stored key before verification
        decrypted_key = decrypt_api_key(api_key.key)
        if verify_password(api_key_value, decrypted_key):
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
    api_key = session.exec(statement).first()
    if api_key:
        # Decrypt the key before returning
        api_key.key = decrypt_api_key(api_key.key)
    return api_key
