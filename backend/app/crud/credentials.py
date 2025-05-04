from typing import Optional, Dict, Any, List
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.models import Credential, CredsCreate, CredsUpdate
from app.core.providers import validate_provider, validate_provider_credentials, get_supported_providers


def set_creds_for_org(*, session: Session, creds_add: CredsCreate) -> Credential:
    """Set credentials for an organization. If provider is specified, add it to the existing credentials."""
    # Validate all providers and their credentials
    if creds_add.credential:
        for provider, credentials in creds_add.credential.items():
            validate_provider(provider)
            validate_provider_credentials(provider, credentials)

    creds = Credential(
        organization_id=creds_add.organization_id,
        is_active=creds_add.is_active,
        credential=creds_add.credential,
    )
    creds.inserted_at = datetime.utcnow()
    try:
        session.add(creds)
        session.commit()
        session.refresh(creds)
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"Error while adding credentials: {str(e)}")
    return creds


def get_key_by_org(*, session: Session, org_id: int) -> Optional[str]:
    """Fetches the API key from the credentials for the given organization."""
    statement = select(Credential).where(Credential.organization_id == org_id)
    creds = session.exec(statement).first()

    # Check if creds exists and if the credential field contains the api_key
    if (
        creds
        and creds.credential
        and "openai" in creds.credential
        and "api_key" in creds.credential["openai"]
    ):
        return creds.credential["openai"]["api_key"]

    return None

def get_creds_by_org(*, session: Session, org_id: int) -> Optional[Credential]:
    """Fetches all credentials for the given organization."""
    statement = select(Credential).where(Credential.organization_id == org_id)
    return session.exec(statement).first()


def get_provider_credential(*, session: Session, org_id: int, provider: str) -> Optional[Dict[str, Any]]:
    """Fetches credentials for a specific provider of an organization."""
    # Validate provider name
    validate_provider(provider)
    
    creds = get_creds_by_org(session=session, org_id=org_id)
    if not creds or not creds.credential:
        return None
    return creds.credential.get(provider)


def get_providers(*, session: Session, org_id: int) -> List[str]:
    """Returns a list of all providers for which credentials are stored."""
    creds = get_creds_by_org(session=session, org_id=org_id)
    if not creds or not creds.credential:
        return []
    return list(creds.credential.keys())


def update_creds_for_org(
    session: Session, org_id: int, creds_in: CredsUpdate
) -> Credential:
    """Update credentials for an organization. Can update specific provider or add new provider."""
    creds = session.exec(
        select(Credential).where(Credential.organization_id == org_id)
    ).first()

    if not creds:
        raise ValueError("Credentials not found")

    # Initialize credential dict if it doesn't exist
    if not creds.credential:
        creds.credential = {}

    # Update provider credentials if provided
    if creds_in.credential:
        if not creds_in.provider:
            raise ValueError("Provider must be specified to update nested credential")
        
        # Validate provider and credentials
        validate_provider(creds_in.provider)
        validate_provider_credentials(creds_in.provider, creds_in.credential)
        
        # Update or add the provider's credentials
        creds.credential[creds_in.provider] = creds_in.credential

    # Update is_active if provided
    if creds_in.is_active is not None:
        creds.is_active = creds_in.is_active

    # Set the updated_at timestamp
    creds.updated_at = datetime.utcnow()

    try:
        session.add(creds)
        session.commit()
        session.refresh(creds)
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"Error while updating credentials: {str(e)}")

    return creds


def remove_provider_credential(
    session: Session, org_id: int, provider: str
) -> Credential:
    """Remove credentials for a specific provider while keeping others intact."""
    # Validate provider name
    validate_provider(provider)
    
    creds = session.exec(
        select(Credential).where(Credential.organization_id == org_id)
    ).first()

    if not creds:
        raise ValueError("Credentials not found")

    if not creds.credential or provider not in creds.credential:
        raise ValueError(f"Provider '{provider}' not found in credentials")

    # Remove the provider's credentials
    del creds.credential[provider]
    creds.updated_at = datetime.utcnow()

    try:
        session.add(creds)
        session.commit()
        session.refresh(creds)
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"Error while removing provider credentials: {str(e)}")

    return creds


def remove_creds_for_org(*, session: Session, org_id: int) -> Optional[Credential]:
    """Removes (soft deletes) all credentials for the given organization while preserving provider structure."""
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.is_active == True
    )
    creds = session.exec(statement).first()

    if creds:
        try:
            creds.is_active = False
            creds.deleted_at = datetime.utcnow()
            # Clear credentials for each provider but keep the provider structure
            if creds.credential:
                for provider in creds.credential:
                    creds.credential[provider] = {}
            session.add(creds)
            session.commit()
            session.refresh(creds)
        except IntegrityError as e:
            session.rollback()
            raise ValueError(f"Error while deleting credentials: {str(e)}")

    return creds
