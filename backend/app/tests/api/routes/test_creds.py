import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
import random
import string

from app.main import app
from app.api.deps import get_db
from app.crud.credentials import set_creds_for_org
from app.models import CredsCreate, Organization, OrganizationCreate
from app.core.config import settings
from app.core.security import encrypt_api_key
from app.core.providers import Provider

client = TestClient(app)


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@pytest.fixture
def create_organization_and_creds(db: Session):
    unique_org_name = "Test Organization " + generate_random_string(5)
    org = Organization(name=unique_org_name, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    api_key = "sk-" + generate_random_string(10)
    creds_data = CredsCreate(
        organization_id=org.id,
        is_active=True,
        credential={
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7
            }
        },
    )
    return org, creds_data


def test_set_creds_for_org(db: Session, superuser_token_headers: dict[str, str]):
    org = Organization(name="Org for Set Creds", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)

    api_key = "sk-" + generate_random_string(10)
    creds_data = {
        "organization_id": org.id,
        "is_active": True,
        "credential": {
            Provider.OPENAI.value: {
                "api_key": api_key,
                "model": "gpt-4",
                "temperature": 0.7
            }
        },
    }

    response = client.post(
        f"{settings.API_V1_STR}/credentials/",
        json=creds_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["organization_id"] == org.id
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4"


def test_read_credentials_with_creds(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["organization_id"] == org.id
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4"


def test_read_credentials_not_found(db: Session, superuser_token_headers: dict[str, str]):
    response = client.get(
        f"{settings.API_V1_STR}/credentials/999999",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Credentials not found"


def test_read_provider_credential(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "gpt-4"
    assert "api_key" in data


def test_read_provider_credential_not_found(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, _ = create_organization_and_creds

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Provider credentials not found"


def test_update_credentials(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4-turbo",
            "temperature": 0.8
        }
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["provider"] == Provider.OPENAI.value
    assert data[0]["credential"]["model"] == "gpt-4-turbo"
    assert data[0]["updated_at"] is not None


def test_update_credentials_not_found(db: Session, superuser_token_headers: dict[str, str]):
    # Create a non-existent organization ID
    non_existent_org_id = 999999

    update_data = {
        "provider": Provider.OPENAI.value,
        "credential": {
            "api_key": "sk-" + generate_random_string(),
            "model": "gpt-4",
            "temperature": 0.7
        }
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{non_existent_org_id}",
        json=update_data,
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Failed to update credentials"


def test_delete_provider_credential(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["message"] == "Provider credentials removed successfully"


def test_delete_provider_credential_not_found(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, _ = create_organization_and_creds

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/{Provider.OPENAI.value}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Provider credentials not found"


def test_delete_all_credentials(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["message"] == "Credentials deleted successfully"

    # Verify the credentials are soft deleted
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["deleted_at"] is not None
    assert data[0]["is_active"] is False
    assert "credential" not in data[0]


def test_delete_all_credentials_not_found(db: Session, superuser_token_headers: dict[str, str]):
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/999999",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Credentials for organization not found"
