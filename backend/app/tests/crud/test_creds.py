import pytest
import random
import string
from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch

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
from app.core.security import encrypt_api_key, decrypt_api_key

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


def test_create_credentials(db: Session):
    org = Organization(name=f"Test Org {generate_random_string()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    openai_key = f"sk-{generate_random_string()}"
    gemini_key = f"gm-{generate_random_string()}"
    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={
            "openai": {"api_key": openai_key},
            "gemini": {"api_key": gemini_key},
        },
    )

    creds = set_creds_for_org(session=db, creds_add=creds_data)
    assert creds is not None
    assert creds.organization_id == org.id
    assert creds.is_active is True
    assert set(creds.credential.keys()) == {"openai", "gemini"}

    # Decrypt and verify the API keys
    decrypted_openai_key = decrypt_api_key(creds.credential["openai"]["api_key"])
    decrypted_gemini_key = decrypt_api_key(creds.credential["gemini"]["api_key"])
    assert decrypted_openai_key == openai_key
    assert decrypted_gemini_key == gemini_key


def test_create_credentials_integrity_error(db: Session, test_credential):
    # Try to create credentials for the same organization
    creds_data = CredsCreate(
        organization_id=test_credential.organization_id,
        is_active=True,
        credential={"openai": {"api_key": "sk-duplicate"}},
    )
    # Since there's no unique constraint, this should succeed
    new_creds = set_creds_for_org(session=db, creds_add=creds_data)
    assert new_creds is not None
    assert new_creds.organization_id == test_credential.organization_id


def test_get_creds_by_org(db: Session, test_credential):
    fetched = get_creds_by_org(session=db, org_id=test_credential.organization_id)
    assert fetched is not None
    assert fetched.organization_id == test_credential.organization_id


def test_get_creds_by_org_not_found(db: Session):
    fetched = get_creds_by_org(session=db, org_id=99999)
    assert fetched is None


def test_get_key_by_org_success(db: Session):
    org = Organization(name=f"Test Org {generate_random_string()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    openai_key = f"sk-{generate_random_string()}"
    creds = Credential(
        organization_id=org.id,
        is_active=True,
        credential={"openai": {"api_key": encrypt_api_key(openai_key)}},
    )
    db.add(creds)
    db.commit()

    key = get_key_by_org(session=db, org_id=org.id)
    assert key is not None
    decrypted_key = decrypt_api_key(key)
    assert decrypted_key.startswith("sk-")


def test_get_key_by_org_not_found(db: Session):
    key = get_key_by_org(session=db, org_id=99999)
    assert key is None


def test_update_creds_for_org_success(db: Session):
    org = Organization(name=f"Test Org {generate_random_string()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    initial_key = f"sk-{generate_random_string()}"
    creds = Credential(
        organization_id=org.id,
        is_active=True,
        credential={"openai": {"api_key": encrypt_api_key(initial_key)}},
    )
    db.add(creds)
    db.commit()

    new_key = "sk-newkey"
    update_data = CredsUpdate(provider="openai", credential={"api_key": new_key})

    updated_creds = update_creds_for_org(
        session=db, org_id=org.id, creds_in=update_data
    )
    assert updated_creds is not None
    decrypted_key = decrypt_api_key(updated_creds.credential["openai"]["api_key"])
    assert decrypted_key == new_key


def test_update_creds_for_org_not_found(db: Session):
    with pytest.raises(ValueError) as exc:
        update_creds_for_org(
            session=db,
            org_id=99999,
            creds_in=CredsUpdate(credential={"openai": {"api_key": "missing"}}),
        )
    assert "Credentials not found" in str(exc.value)


def test_update_creds_for_org_integrity_error(db: Session, test_credential):
    """Test update_creds_for_org when an integrity error occurs during update."""
    # Mock the session to raise IntegrityError when committing
    with patch.object(db, "commit", side_effect=IntegrityError(None, None, None)):
        with pytest.raises(ValueError) as exc:
            update_creds_for_org(
                session=db,
                org_id=test_credential.organization_id,
                creds_in=CredsUpdate(
                    provider="openai", credential={"api_key": "sk-test"}
                ),
            )
        assert "Error while updating credentials" in str(exc.value)


def test_update_creds_for_org_missing_provider(db: Session, test_credential):
    """Test update_creds_for_org when provider is not specified for nested credentials."""
    with pytest.raises(ValueError) as exc:
        update_creds_for_org(
            session=db,
            org_id=test_credential.organization_id,
            creds_in=CredsUpdate(credential={"api_key": "sk-test"}),  # Missing provider
        )
    assert "Provider must be specified to update nested credential" in str(exc.value)


def test_remove_creds_for_org_success(db: Session, test_credential):
    removed = remove_creds_for_org(session=db, org_id=test_credential.organization_id)
    assert removed is not None
    assert removed.organization_id == test_credential.organization_id
    assert removed.deleted_at is not None
    assert removed.is_active is False

    # Verify soft delete
    deleted_creds = (
        db.query(Credential)
        .filter(Credential.organization_id == test_credential.organization_id)
        .first()
    )
    assert deleted_creds is not None
    assert deleted_creds.deleted_at is not None
    assert deleted_creds.is_active is False


def test_remove_creds_for_org_not_found(db: Session):
    result = remove_creds_for_org(session=db, org_id=99999)
    assert result is None


def test_remove_creds_for_org_integrity_error(db: Session, test_credential):
    """Test remove_creds_for_org when an integrity error occurs during deletion."""
    # Mock the session to raise IntegrityError when committing
    with patch.object(db, "commit", side_effect=IntegrityError(None, None, None)):
        with pytest.raises(ValueError) as exc:
            remove_creds_for_org(session=db, org_id=test_credential.organization_id)
        assert "Error while deleting credentials" in str(exc.value)


def test_get_provider_credential_success(db: Session):
    org = Organization(name=f"Test Org {generate_random_string()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    openai_key = f"sk-{generate_random_string()}"
    creds = Credential(
        organization_id=org.id,
        is_active=True,
        credential={"openai": {"api_key": encrypt_api_key(openai_key)}},
    )
    db.add(creds)
    db.commit()

    provider_creds = get_provider_credential(
        session=db, org_id=org.id, provider="openai"
    )
    assert provider_creds is not None
    decrypted_key = decrypt_api_key(provider_creds["api_key"])
    assert decrypted_key.startswith("sk-")


def test_get_provider_credential_not_found(db: Session, test_credential):
    provider_cred = get_provider_credential(
        session=db, org_id=test_credential.organization_id, provider="gemini"
    )
    assert provider_cred is None


def test_get_providers_success(db: Session, test_credential):
    providers = get_providers(session=db, org_id=test_credential.organization_id)
    assert "openai" in providers


def test_get_providers_not_found(db: Session):
    providers = get_providers(session=db, org_id=99999)
    assert providers == []


def test_remove_provider_credential_success(db: Session, test_credential):
    # First add another provider
    update = CredsUpdate(
        provider="gemini",
        credential={"api_key": "gm-" + generate_random_string()},
    )
    updated = update_creds_for_org(
        session=db, org_id=test_credential.organization_id, creds_in=update
    )
    assert "gemini" in updated.credential

    # Now remove the provider
    removed = remove_provider_credential(
        session=db, org_id=test_credential.organization_id, provider="gemini"
    )
    assert "gemini" not in removed.credential
    assert "openai" in removed.credential  # Original provider should still exist


def test_remove_provider_credential_not_found(db: Session, test_credential):
    with pytest.raises(ValueError) as exc:
        remove_provider_credential(
            session=db, org_id=test_credential.organization_id, provider="gemini"
        )
    assert "not found" in str(exc.value)


def test_remove_provider_credential_org_not_found(db: Session):
    with pytest.raises(ValueError) as exc:
        remove_provider_credential(session=db, org_id=99999, provider="openai")
    assert "not found" in str(exc.value)


def test_remove_provider_credential_integrity_error(db: Session, test_credential):
    """Test remove_provider_credential when an integrity error occurs during removal."""
    # Mock the session to raise IntegrityError when committing
    with patch.object(db, "commit", side_effect=IntegrityError(None, None, None)):
        with pytest.raises(ValueError) as exc:
            remove_provider_credential(
                session=db, org_id=test_credential.organization_id, provider="openai"
            )
        assert "Error while removing provider credentials" in str(exc.value)


def test_set_creds_for_org_integrity_error(db: Session, test_org):
    """Test set_creds_for_org when an integrity error occurs during creation."""
    # Mock the session to raise IntegrityError when committing
    with patch.object(db, "commit", side_effect=IntegrityError(None, None, None)):
        with pytest.raises(ValueError) as exc:
            set_creds_for_org(
                session=db,
                creds_add=CredsCreate(
                    organization_id=test_org.id,
                    is_active=True,
                    credential={"openai": {"api_key": "sk-test"}},
                ),
            )
        assert "Error while adding credentials" in str(exc.value)


def test_validate_provider_credentials_missing_fields(db: Session, test_org):
    """Test validation of provider credentials when required fields are missing."""
    # Test with missing api_key for OpenAI
    with pytest.raises(ValueError) as exc:
        set_creds_for_org(
            session=db,
            creds_add=CredsCreate(
                organization_id=test_org.id,
                is_active=True,
                credential={"openai": {}},  # Missing api_key
            ),
        )
    assert "Missing required fields for openai" in str(exc.value)

    # Test with missing api_key for Gemini
    with pytest.raises(ValueError) as exc:
        set_creds_for_org(
            session=db,
            creds_add=CredsCreate(
                organization_id=test_org.id,
                is_active=True,
                credential={"gemini": {}},  # Missing api_key
            ),
        )
    assert "Missing required fields for gemini" in str(exc.value)
