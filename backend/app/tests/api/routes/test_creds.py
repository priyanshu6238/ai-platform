import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
import random
import string, datetime
from sqlalchemy import select

from app.main import app
from app.api.deps import get_db
from app.crud.credentials import (
    set_creds_for_org,
    get_creds_by_org,
    remove_creds_for_org,
)
from app.models import (
    CredsCreate,
    CredsUpdate,
    Organization,
    OrganizationCreate,
    Credential,
)
from app.utils import APIResponse
from app.tests.utils.utils import random_lower_string
from app.core.config import settings

client = TestClient(app)


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def create_organization_and_creds(db: Session, superuser_token_headers: dict[str, str]):
    unique_org_name = "Test Organization " + generate_random_string(5)
    org_data = OrganizationCreate(name=unique_org_name, is_active=True)
    org = Organization(**org_data.dict())
    db.add(org)
    db.commit()
    db.refresh(org)

    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={
            "openai": {"api_key": "sk-" + generate_random_string(10)},
            "gemini": {"api_key": "gemini-" + generate_random_string(10)},
        },
    )
    return org, creds_data


def test_create_credentials(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data.dict(),
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["organization_id"] == org.id
    assert "openai" in data["data"]["credential"]
    assert "gemini" in data["data"]["credential"]


def test_read_credential(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["organization_id"] == org.id
    assert "openai" in data["data"]["credential"]
    assert "gemini" in data["data"]["credential"]


def test_read_provider_credential(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    # Test reading OpenAI credentials
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/openai",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["api_key"] == creds_data.credential["openai"]["api_key"]

    # Test reading Gemini credentials
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/gemini",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["api_key"] == creds_data.credential["gemini"]["api_key"]


def test_read_provider_credential_not_found(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, _ = create_organization_and_creds

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/invalid_provider",
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Unsupported provider: invalid_provider" in data["error"]
    assert "Supported providers are:" in data["error"]


def test_update_credential(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    update_data = CredsUpdate(provider="openai", credential={"api_key": "sk-updated"})

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        json=update_data.dict(),
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["credential"]["openai"]["api_key"] == "sk-updated"
    assert "gemini" in data["data"]["credential"]


def test_delete_provider_credential(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/openai",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["message"] == "Provider credentials removed successfully"

    # Verify the provider was removed
    updated_creds = get_creds_by_org(session=db, org_id=org.id)
    assert "openai" not in updated_creds.credential
    assert "gemini" in updated_creds.credential


def test_delete_all_credentials(
    db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds
):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    # Delete all credentials
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["message"] == "Credentials deleted successfully"

    # Verify credentials are marked as inactive but still accessible
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["is_active"] is False
    assert data["data"]["deleted_at"] is not None
    # Verify providers are preserved but credentials are cleared
    assert "openai" in data["data"]["credential"]
    assert "gemini" in data["data"]["credential"]
    assert data["data"]["credential"]["openai"] == {}
    assert data["data"]["credential"]["gemini"] == {}
