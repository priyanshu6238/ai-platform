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
    CredsUpdate,
    Organization,
    OrganizationCreate,
)
from app.crud.credentials import (
    set_creds_for_org,
    get_creds_by_org,
    get_key_by_org,
    remove_creds_for_org,
    update_creds_for_org,
)
from app.main import app
from app.utils import APIResponse

client = TestClient(app)


# Helper function to generate random API key
def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def test_credential(db: Session):
    # Create a unique organization
    unique_org_name = "TestOrg_" + generate_random_string(6)
    org = Organization(name=unique_org_name, is_active=True)
    db.add(org)

    try:
        db.commit()
        db.refresh(org)
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Error during organization commit: {str(e)}")

    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={"openai": {"api_key": "sk-" + generate_random_string(12)}},
    )

    creds = set_creds_for_org(session=db, creds_add=creds_data)
    return creds


def test_create_credentials(db: Session, test_credential):
    creds = test_credential
    assert creds is not None
    assert "openai" in creds.credential
    assert creds.credential["openai"]["api_key"].startswith("sk-")
    assert creds.inserted_at is not None


def test_get_creds_by_org(db: Session, test_credential):
    creds = test_credential
    fetched = get_creds_by_org(session=db, org_id=creds.organization_id)
    assert fetched is not None
    assert fetched.organization_id == creds.organization_id
    assert "openai" in fetched.credential


def test_update_creds_for_org_add_provider(db: Session, test_credential):
    # Add new provider: "gemini"
    update = CredsUpdate(
        provider="gemini",
        credential={"api_key": "gm-" + generate_random_string(12)},
    )
    updated = update_creds_for_org(
        session=db, org_id=test_credential.organization_id, creds_in=update
    )

    assert updated is not None
    assert "gemini" in updated.credential
    assert updated.credential["gemini"]["api_key"].startswith("gm-")


def test_update_creds_for_org_replace_provider(db: Session, test_credential):
    # Replace OpenAI provider's API key
    new_key = "sk-newkey"
    update = CredsUpdate(
        provider="openai",
        credential={"api_key": new_key},
    )
    updated = update_creds_for_org(
        session=db, org_id=test_credential.organization_id, creds_in=update
    )

    assert updated is not None
    assert updated.credential["openai"]["api_key"] == new_key


def test_remove_all_credentials(db: Session, test_credential):
    org_id = test_credential.organization_id
    removed = remove_creds_for_org(session=db, org_id=org_id)

    assert removed is not None
    assert removed.is_active is False
    assert removed.deleted_at is not None
    assert all(
        creds == {} for creds in removed.credential.values()
    )  # All providers' creds cleared


def test_get_key_by_org(db: Session, test_credential):
    key = get_key_by_org(session=db, org_id=test_credential.organization_id)
    assert key is not None
    assert key.startswith("sk-")
