import uuid
import pytest
from sqlmodel import Session, select
from app.crud import api_key as api_key_crud
from app.models import APIKey, User, Organization
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash, verify_password


# Helper function to create a user
def create_test_user(db: Session) -> User:
    user = User(email=random_email(), hashed_password=get_password_hash("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# Helper function to create an organization
def create_test_organization(db: Session) -> Organization:
    org = Organization(name="Test Organization")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def test_create_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)

    assert api_key.key.startswith("ApiKey ")
    assert len(api_key.key) > 32
    assert api_key.organization_id == org.id
    assert api_key.user_id == user.id
    assert verify_password(api_key.key, api_key.hashed_key)


def test_get_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    created_key = api_key_crud.create_api_key(db, org.id, user.id)
    retrieved_key = api_key_crud.get_api_key(db, created_key.id)

    assert retrieved_key is not None
    assert retrieved_key.id == created_key.id
    assert retrieved_key.key == created_key.key
    assert verify_password(retrieved_key.key, retrieved_key.hashed_key)


def test_get_api_key_not_found(db: Session) -> None:
    result = api_key_crud.get_api_key(db, 9999)  # Non-existent ID
    assert result is None


def test_get_api_keys_by_organization(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    # Create multiple API keys
    api_key1 = api_key_crud.create_api_key(db, org.id, user.id)
    api_key2 = api_key_crud.create_api_key(db, org.id, user.id)

    api_keys = api_key_crud.get_api_keys_by_organization(db, org.id)

    assert len(api_keys) == 2
    assert any(ak.id == api_key1.id for ak in api_keys)
    assert any(ak.id == api_key2.id for ak in api_keys)
    for ak in api_keys:
        assert verify_password(ak.key, ak.hashed_key)


def test_delete_api_key(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)
    api_key_crud.delete_api_key(db, api_key.id)

    # Verify the key is soft deleted
    deleted_key = db.get(APIKey, api_key.id)
    assert deleted_key is not None
    assert deleted_key.is_deleted is True
    assert deleted_key.deleted_at is not None


def test_delete_api_key_already_deleted(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)
    api_key_crud.delete_api_key(db, api_key.id)

    with pytest.raises(ValueError, match="API key not found or already deleted"):
        api_key_crud.delete_api_key(db, api_key.id)


def test_get_api_key_by_value(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    # Create an API key
    api_key = api_key_crud.create_api_key(db, org.id, user.id)
    # Get the raw key that was returned during creation
    raw_key = api_key.key

    # Test retrieving the API key by its value
    retrieved_key = api_key_crud.get_api_key_by_value(db, raw_key)

    assert retrieved_key is not None
    assert retrieved_key.id == api_key.id
    assert verify_password(api_key.key, retrieved_key.hashed_key)


def test_get_api_key_by_user_org(db: Session) -> None:
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)
    retrieved_key = api_key_crud.get_api_key_by_user_org(db, org.id, user.id)

    assert retrieved_key is not None
    assert retrieved_key.id == api_key.id
    assert retrieved_key.organization_id == org.id
    assert retrieved_key.user_id == user.id
    assert verify_password(retrieved_key.key, retrieved_key.hashed_key)


def test_get_api_key_by_user_org_not_found(db: Session) -> None:
    org = create_test_organization(db)
    user_id = uuid.uuid4()
    result = api_key_crud.get_api_key_by_user_org(db, org.id, user_id)
    assert result is None
