import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
import random
import string

from app.main import app
from app.api.deps import get_db
from app.crud.credentials import set_creds_for_org, get_creds_by_org
from app.models import (
    CredsCreate,
    CredsUpdate,
    Organization,
    OrganizationCreate,
    Credential,
)
from app.core.config import settings
from app.tests.utils.utils import random_lower_string

client = TestClient(app)


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def create_organization_and_creds(db: Session):
    """Fixture to create an organization and sample credentials."""
    unique_org_name = f"Test Org {generate_random_string(5)}"
    org = Organization(name=unique_org_name, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={
            "openai": {"api_key": f"sk-{generate_random_string()}"},
            "gemini": {"api_key": f"gm-{generate_random_string()}"},
        },
    )
    return org, creds_data


def test_create_credentials(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, creds_data = create_organization_and_creds

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data.dict(),
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"]
    assert data["data"]["organization_id"] == org.id
    assert set(data["data"]["credential"].keys()) == {"openai", "gemini"}


def test_read_all_credentials(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"]
    assert data["data"]["organization_id"] == org.id
    assert "openai" in data["data"]["credential"]
    assert "gemini" in data["data"]["credential"]


def test_read_single_provider_credentials(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    for provider in ["openai", "gemini"]:
        response = client.get(
            f"{settings.API_V1_STR}/credentials/{org.id}/{provider}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert data["data"]["api_key"] == creds_data.credential[provider]["api_key"]


def test_read_provider_invalid_or_not_found(db: Session, superuser_token_headers: dict):
    # Setup: Only OpenAI creds
    org = Organization(name=f"Test Org {random_lower_string()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={"openai": {"api_key": "sk-test-key"}},
    )
    set_creds_for_org(session=db, creds_add=creds_data)

    # Unsupported provider
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/unsupported",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "Unsupported provider" in response.json()["error"]

    # Supported provider but not added
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/gemini",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "Provider credentials not found" in response.json()["error"]


def test_update_provider_credentials(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    update_payload = CredsUpdate(
        provider="openai", credential={"api_key": "sk-updated"}
    )

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        json=update_payload.dict(),
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"]
    assert data["data"]["credential"]["openai"]["api_key"] == "sk-updated"
    assert "gemini" in data["data"]["credential"]


def test_update_invalid_provider(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, _ = create_organization_and_creds

    # Create OpenAI only
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json={"organization_id": org.id, "credential": {"openai": {"api_key": "init"}}},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Try invalid provider update
    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        json={"provider": "invalid", "credential": {"api_key": "fail"}},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "Unsupported provider" in response.json()["error"]


def test_delete_single_provider(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/openai",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert (
        response.json()["data"]["message"]
        == "Provider credentials removed successfully"
    )

    updated_creds = get_creds_by_org(session=db, org_id=org.id)
    assert "openai" not in updated_creds.credential
    assert "gemini" in updated_creds.credential


def test_delete_invalid_provider(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, _ = create_organization_and_creds
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/invalid_provider",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "Unsupported provider" in response.json()["error"]


def test_delete_all_credentials(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["message"] == "Credentials deleted successfully"

    # Check soft-deletion
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )
    data = response.json()
    assert not data["data"]["is_active"]
    assert data["data"]["deleted_at"]
    assert data["data"]["credential"]["openai"] == {}
    assert data["data"]["credential"]["gemini"] == {}


def test_create_credential_with_invalid_provider(
    db: Session, superuser_token_headers: dict, create_organization_and_creds
):
    org, _ = create_organization_and_creds
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json={
            "organization_id": org.id,
            "credential": {"invalid_provider": {"api_key": "bad"}},
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "Unsupported provider" in response.json()["error"]


def test_create_credential_for_new_organization(
    db: Session, superuser_token_headers: dict
):
    org = Organization(name=f"Test Org {random_lower_string()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    payload = {
        "organization_id": org.id,
        "is_active": True,
        "credential": {
            "openai": {"api_key": "sk-test"},
            "gemini": {"api_key": "gm-test"},
        },
    }

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=payload,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"]
    assert data["data"]["organization_id"] == org.id
    assert data["data"]["credential"]["openai"]["api_key"] == "sk-test"
    assert data["data"]["credential"]["gemini"]["api_key"] == "gm-test"


def test_create_credential_organization_not_found(db: Session, superuser_token_headers: dict):
    """Test creating credentials for a non-existent organization."""
    creds_data = {
        "organization_id": 999999,  # Non-existent organization ID
        "is_active": True,
        "credential": {"openai": {"api_key": "sk-" + generate_random_string(10)}},
    }

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data,
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "Error while adding credentials" in data["error"]
    assert "ForeignKeyViolation" in data["error"]


def test_read_credential_not_found(db: Session, superuser_token_headers: dict):
    """Test reading non-existent credentials."""
    response = client.get(
        f"{settings.API_V1_STR}/credentials/999999",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "Credentials not found" in data["error"]


def test_update_credential_not_found(db: Session, superuser_token_headers: dict):
    """Test updating non-existent credentials."""
    update_data = {
        "credential": {"openai": {"api_key": "sk-" + generate_random_string(10)}}
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/999999",
        json=update_data,
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "Credentials not found" in data["error"]


def test_delete_provider_credential_not_found(db: Session, superuser_token_headers: dict):
    """Test deleting non-existent provider credentials."""
    org = Organization(name=f"Test Org {random_lower_string()}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    # Use a valid provider name but non-existent credentials
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/openai",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Credentials not found" in data["error"]


def test_delete_all_credentials_not_found(db: Session, superuser_token_headers: dict):
    """Test deleting non-existent credentials."""
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/999999",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "Credentials for organization not found" in data["error"]
