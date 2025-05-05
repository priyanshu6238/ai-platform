import pytest
import random
import string
from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError

from app.models import Credential, CredsCreate, CredsUpdate, Organization
from app.crud.credentials import (
    set_creds_for_org,
    get_creds_by_org,
    get_key_by_org,
    remove_creds_for_org,
    update_creds_for_org,
    remove_provider_credential,
    get_providers,
    get_provider_credential,
)
from app.main import app

client = TestClient(app)

def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

@pytest.fixture
def test_org(db: Session):
    name = "Org_" + generate_random_string()
    org = Organization(name=name, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org

@pytest.fixture
def test_credential(db: Session, test_org):
    creds_data = CredsCreate(
        organization_id=test_org.id,
        is_active=True,
        credential={"openai": {"api_key": "sk-" + generate_random_string(12)}},
    )
    creds = set_creds_for_org(session=db, creds_add=creds_data)
    return creds

def test_create_credentials(db: Session, test_credential):
    assert test_credential is not None
    assert "openai" in test_credential.credential
    assert test_credential.credential["openai"]["api_key"].startswith("sk-")

def test_get_creds_by_org(db: Session, test_credential):
    fetched = get_creds_by_org(session=db, org_id=test_credential.organization_id)
    assert fetched is not None
    assert fetched.organization_id == test_credential.organization_id

def test_get_key_by_org_success(db: Session, test_credential):
    key = get_key_by_org(session=db, org_id=test_credential.organization_id)
    assert key is not None and key.startswith("sk-")

def test_get_key_by_org_missing_provider(db: Session, test_org):
    key = get_key_by_org(session=db, org_id=test_org.id)
    assert key is None

def test_update_creds_for_org_add_provider(db: Session, test_credential):
    update = CredsUpdate(provider="gemini", credential={"api_key": "gm-" + generate_random_string()})
    updated = update_creds_for_org(session=db, org_id=test_credential.organization_id, creds_in=update)
    assert "gemini" in updated.credential

def test_update_creds_for_org_replace_provider(db: Session, test_credential):
    update = CredsUpdate(provider="openai", credential={"api_key": "sk-replaced"})
    updated = update_creds_for_org(session=db, org_id=test_credential.organization_id, creds_in=update)
    assert updated.credential["openai"]["api_key"] == "sk-replaced"

def test_update_creds_missing_provider_raises(db: Session, test_credential):
    with pytest.raises(ValueError, match="Provider must be specified"):
        update_creds_for_org(session=db, org_id=test_credential.organization_id, creds_in=CredsUpdate(credential={"api_key": "x"}))

def test_remove_all_credentials(db: Session, test_credential):
    removed = remove_creds_for_org(session=db, org_id=test_credential.organization_id)
    assert not removed.is_active
    assert removed.deleted_at is not None
    assert all(val == {} for val in removed.credential.values())

def test_remove_all_credentials_no_creds(db: Session, test_org):
    creds = CredsCreate(organization_id=test_org.id, is_active=True, credential={})
    set_creds_for_org(session=db, creds_add=creds)
    removed = remove_creds_for_org(session=db, org_id=test_org.id)
    assert removed is not None
    assert removed.credential == {}

def test_get_provider_credential_found(db: Session, test_credential):
    cred = get_provider_credential(session=db, org_id=test_credential.organization_id, provider="openai")
    assert cred["api_key"].startswith("sk-")

def test_get_provider_credential_not_found(db: Session, test_credential):
    cred = get_provider_credential(session=db, org_id=test_credential.organization_id, provider="gemini")
    assert cred is None

def test_get_providers(db: Session, test_credential):
    providers = get_providers(session=db, org_id=test_credential.organization_id)
    assert "openai" in providers

def test_get_providers_empty(db: Session, test_org):
    assert get_providers(session=db, org_id=test_org.id) == []

def test_remove_provider_credential_success(db: Session, test_credential):
    update = CredsUpdate(provider="gemini", credential={"api_key": "gm-123"})
    update_creds_for_org(session=db, org_id=test_credential.organization_id, creds_in=update)
    removed = remove_provider_credential(session=db, org_id=test_credential.organization_id, provider="gemini")
    assert "gemini" not in removed.credential or removed.credential["gemini"] == {}

def test_remove_provider_credential_not_found(db: Session, test_credential):
    with pytest.raises(ValueError, match="not found"):
        remove_provider_credential(session=db, org_id=test_credential.organization_id, provider="gemini")

def test_update_creds_for_org_not_found(db: Session):
    with pytest.raises(ValueError, match="Credentials not found"):
        update_creds_for_org(session=db, org_id=99999, creds_in=CredsUpdate(provider="openai", credential={"api_key": "123"}))

def test_remove_provider_creds_org_not_found(db: Session):
    with pytest.raises(ValueError, match="Credentials not found"):
        remove_provider_credential(session=db, org_id=99999, provider="openai")

def test_set_invalid_provider_raises(db: Session, test_org):
    creds = CredsCreate(
        organization_id=test_org.id,
        is_active=True,
        credential={"unknown_provider": {"api_key": "123"}},
    )
    with pytest.raises(ValueError, match="Unsupported provider"):
        set_creds_for_org(session=db, creds_add=creds)

def test_update_invalid_provider_raises(db: Session, test_credential):
    update = CredsUpdate(provider="invalid123", credential={"api_key": "x"})
    with pytest.raises(ValueError, match="Unsupported provider"):
        update_creds_for_org(session=db, org_id=test_credential.organization_id, creds_in=update)
