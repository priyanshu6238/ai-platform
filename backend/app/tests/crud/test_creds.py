import pytest
import random
import string
from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.models import (
    Credential,
    CredsCreate,
    Organization,
    OrganizationCreate,
    CredsUpdate,
)
from app.crud.credentials import (
    set_creds_for_org,
    get_creds_by_org,
    get_key_by_org,
    get_provider_credential,
    get_providers,
    remove_creds_for_org,
    update_creds_for_org,
    remove_provider_credential,
)
from app.main import app
from app.utils import APIResponse
from app.core.config import settings

client = TestClient(app)


# Helper function to generate random API key
def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def test_credential(db: Session):
    # Create a unique organization name
    unique_org_name = "Test Organization " + generate_random_string(5)

    # Check if the organization already exists by name
    existing_org = (
        db.query(Organization).filter(Organization.name == unique_org_name).first()
    )

    if existing_org:
        org = existing_org
    else:
        organization_data = OrganizationCreate(name=unique_org_name, is_active=True)
        org = Organization(**organization_data.dict())
        db.add(org)

        try:
            db.commit()
            db.refresh(org)
        except IntegrityError as e:
            db.rollback()
            raise ValueError(f"Error during organization commit: {str(e)}")

    # Create credentials for multiple providers
    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={
            "openai": {"api_key": "sk-" + generate_random_string(10)},
            "gemini": {"api_key": "gemini-" + generate_random_string(10)},
        },
    )

    creds = set_creds_for_org(session=db, creds_add=creds_data)
    return creds


def test_create_credentials(db: Session, test_credential):
    creds = test_credential
    assert creds is not None
    assert "openai" in creds.credential
    assert "gemini" in creds.credential
    assert creds.credential["openai"]["api_key"].startswith("sk-")
    assert creds.credential["gemini"]["api_key"].startswith("gemini-")
    assert creds.is_active is True
    assert creds.inserted_at is not None


def test_get_creds_by_org(db: Session, test_credential):
    creds = test_credential
    retrieved_creds = get_creds_by_org(session=db, org_id=creds.organization_id)

    assert retrieved_creds is not None
    assert retrieved_creds.organization_id == creds.organization_id
    assert "openai" in retrieved_creds.credential
    assert "gemini" in retrieved_creds.credential
    assert retrieved_creds.inserted_at is not None


def test_get_provider_credential(db: Session, test_credential):
    creds = test_credential
    openai_cred = get_provider_credential(
        session=db, org_id=creds.organization_id, provider="openai"
    )
    gemini_cred = get_provider_credential(
        session=db, org_id=creds.organization_id, provider="gemini"
    )

    assert openai_cred is not None
    assert gemini_cred is not None
    assert openai_cred["api_key"].startswith("sk-")
    assert gemini_cred["api_key"].startswith("gemini-")


def test_get_providers(db: Session, test_credential):
    creds = test_credential
    providers = get_providers(session=db, org_id=creds.organization_id)

    assert len(providers) == 2
    assert "openai" in providers
    assert "gemini" in providers


def test_update_creds_for_org(db: Session, test_credential):
    creds = test_credential
    updated_creds_data = CredsUpdate(
        provider="openai", credential={"api_key": "sk-newkey"}
    )

    updated_creds = update_creds_for_org(
        session=db, org_id=creds.organization_id, creds_in=updated_creds_data
    )

    assert updated_creds is not None
    assert updated_creds.credential["openai"]["api_key"] == "sk-newkey"
    assert updated_creds.credential["gemini"]["api_key"].startswith("gemini-")
    assert updated_creds.updated_at is not None


def test_remove_provider_credential(db: Session, test_credential):
    creds = test_credential
    updated_creds = remove_provider_credential(
        session=db, org_id=creds.organization_id, provider="openai"
    )

    assert updated_creds is not None
    assert "openai" not in updated_creds.credential
    assert "gemini" in updated_creds.credential
    assert updated_creds.updated_at is not None


def test_remove_creds_for_org(db: Session, test_credential):
    creds = test_credential
    removed_creds = remove_creds_for_org(session=db, org_id=creds.organization_id)

    assert removed_creds is not None
    assert removed_creds.organization_id == creds.organization_id
    assert removed_creds.deleted_at is not None
    assert removed_creds.is_active is False
    # Verify providers are preserved but credentials are cleared
    assert "openai" in removed_creds.credential
    assert "gemini" in removed_creds.credential
    assert removed_creds.credential["openai"] == {}
    assert removed_creds.credential["gemini"] == {}


def test_remove_creds_for_org_not_found(db: Session):
    non_existing_org_id = 999
    removed_creds = remove_creds_for_org(session=db, org_id=non_existing_org_id)
    assert removed_creds is None


def test_get_key_by_org_invalid_provider(db: Session, test_credential: Credential):
    """Test getting API key with invalid provider."""
    # First remove existing credentials
    remove_creds_for_org(session=db, org_id=test_credential.organization_id)

    # Create credentials with only gemini provider
    creds = CredsCreate(
        organization_id=test_credential.organization_id,
        credential={"gemini": {"api_key": "test-gemini-key"}},
    )
    set_creds_for_org(session=db, creds_add=creds)

    # Try to get openai key when only gemini exists
    key = get_key_by_org(session=db, org_id=test_credential.organization_id)
    assert key is None


def test_update_creds_invalid_provider(db: Session, test_credential: Credential):
    """Test updating credentials with invalid provider."""
    # Try to update with invalid provider
    with pytest.raises(ValueError) as exc_info:
        update_creds_for_org(
            session=db,
            org_id=test_credential.organization_id,
            creds_in=CredsUpdate(
                provider="invalid_provider", credential={"api_key": "new-key"}
            ),
        )
    assert "Unsupported provider" in str(exc_info.value)


def test_remove_provider_not_found(db: Session, test_credential: Credential):
    """Test removing non-existent provider credentials."""
    # Try to remove non-existent provider
    with pytest.raises(ValueError) as exc_info:
        remove_provider_credential(
            session=db,
            org_id=test_credential.organization_id,
            provider="invalid_provider",
        )
    assert "Unsupported provider" in str(exc_info.value)


def test_remove_creds_not_found(db: Session):
    """Test removing credentials for non-existent organization."""
    # Try to remove credentials for non-existent org
    result = remove_creds_for_org(session=db, org_id=999999)
    assert result is None
