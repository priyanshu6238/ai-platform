from typing import Dict, List, Optional
from enum import Enum


class Provider(str, Enum):
    """Enumeration of supported credential providers."""

    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    MISTRAL = "mistral"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    AZURE = "azure"
    AWS = "aws"
    GOOGLE = "google"


# Required fields for each provider's credentials
PROVIDER_REQUIRED_FIELDS: Dict[str, List[str]] = {
    Provider.OPENAI: ["api_key"],
    Provider.GEMINI: ["api_key"],
    Provider.ANTHROPIC: ["api_key"],
    Provider.MISTRAL: ["api_key"],
    Provider.COHERE: ["api_key"],
    Provider.HUGGINGFACE: ["api_key"],
    Provider.AZURE: ["api_key", "endpoint"],
    Provider.AWS: ["access_key_id", "secret_access_key", "region"],
    Provider.GOOGLE: ["api_key"],
}


def validate_provider(provider: str) -> Provider:
    """Validate that the provider name is supported and return the Provider enum."""
    try:
        return Provider(provider.lower())
    except ValueError:
        supported = ", ".join([p.value for p in Provider])
        raise ValueError(
            f"Unsupported provider: {provider}. Supported providers are: {supported}"
        )


def validate_provider_credentials(provider: str, credentials: dict) -> None:
    """Validate that the credentials contain all required fields for the provider."""
    provider_enum = validate_provider(provider)
    required_fields = PROVIDER_REQUIRED_FIELDS[provider_enum]

    missing_fields = [field for field in required_fields if field not in credentials]
    if missing_fields:
        raise ValueError(
            f"Missing required fields for {provider}: {', '.join(missing_fields)}"
        )


def get_supported_providers() -> List[str]:
    """Return a list of all supported provider names."""
    return [p.value for p in Provider]