import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.main import app
from app.models import APIKey, User, Organization
from app.core.config import settings
from app.crud import api_key as api_key_crud
from app.tests.utils.utils import random_email
from app.core.security import get_password_hash, verify_password

client = TestClient(app)


def create_test_user(db: Session) -> User:
    user = User(
        email=random_email(),
        hashed_password=get_password_hash("password123"),
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_organization(db: Session) -> Organization:
    org = Organization(name="Test Organization")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def test_create_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    response = client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "id" in data["data"]
    assert "key" in data["data"]
    assert "hashed_key" in data["data"]
    assert data["data"]["organization_id"] == org.id
    assert data["data"]["user_id"] == str(user.id)
    assert verify_password(data["data"]["key"], data["data"]["hashed_key"])


def test_create_duplicate_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    response = client.post(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "API Key already exists" in response.json()["detail"]


def test_list_api_keys(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    # Create an API key first
    api_key = api_key_crud.create_api_key(db, org.id, user.id)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys",
        params={"organization_id": org.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == api_key.id
    assert verify_password(data["data"][0]["key"], data["data"][0]["hashed_key"])


def test_get_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys/{api_key.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == api_key.id
    assert verify_password(data["data"]["key"], data["data"]["hashed_key"])


def test_get_nonexistent_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    response = client.get(
        f"{settings.API_V1_STR}/apikeys/999999",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "API Key does not exist" in response.json()["detail"]


def test_revoke_api_key(db: Session, superuser_token_headers: dict[str, str]):
    user = create_test_user(db)
    org = create_test_organization(db)

    api_key = api_key_crud.create_api_key(db, org.id, user.id)

    response = client.delete(
        f"{settings.API_V1_STR}/apikeys/{api_key.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["message"] == "API key revoked successfully"


def test_revoke_nonexistent_api_key(
    db: Session, superuser_token_headers: dict[str, str]
):
    user = create_test_user(db)
    org = create_test_organization(db)

    response = client.delete(
        f"{settings.API_V1_STR}/apikeys/999999",
        params={"organization_id": org.id, "user_id": user.id},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "API key not found or already deleted" in response.json()["detail"]
