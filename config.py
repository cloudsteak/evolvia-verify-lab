import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    provider: str
    azure_subscription_id: str | None = None
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None
    aws_region: str | None = None
    aws_account_id: str | None = None
    gcp_project_id: str | None = None
    internal_api_key: str | None = None


def _require_env(value: str | None, env_name: str, provider: str) -> str:
    if value is None:
        raise RuntimeError(
            f"Missing required environment variable '{env_name}' for provider '{provider}'."
        )
    return value


def _get_internal_api_key(provider: str) -> str | None:
    provider_specific_env = {
        "azure": "INTERNAL_VERIFY_AZURE_API_KEY",
        "aws": "INTERNAL_VERIFY_AWS_API_KEY",
        "gcp": "INTERNAL_VERIFY_GCP_API_KEY",
    }

    provider_key = os.getenv(provider_specific_env[provider], None)
    if provider_key is not None:
        return provider_key

    return os.getenv("INTERNAL_VERIFY_API_KEY", None)


def get_settings() -> Settings:
    provider = os.getenv("PROVIDER", "azure")

    if provider not in {"azure", "aws", "gcp"}:
        raise RuntimeError(
            "Invalid PROVIDER value. Expected one of: azure, aws, gcp."
        )

    settings = Settings(
        provider=provider,
        azure_subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", None),
        azure_tenant_id=os.getenv("AZURE_TENANT_ID", None),
        azure_client_id=os.getenv("AZURE_CLIENT_ID", None),
        azure_client_secret=os.getenv("AZURE_CLIENT_SECRET", None),
        aws_region=os.getenv("AWS_REGION", None),
        aws_account_id=os.getenv("AWS_ACCOUNT_ID", None),
        gcp_project_id=os.getenv("GCP_PROJECT_ID", None),
        internal_api_key=_get_internal_api_key(provider),
    )

    if provider == "azure":
        _require_env(settings.azure_subscription_id, "AZURE_SUBSCRIPTION_ID", provider)
        _require_env(settings.azure_tenant_id, "AZURE_TENANT_ID", provider)
        _require_env(settings.azure_client_id, "AZURE_CLIENT_ID", provider)
        _require_env(settings.azure_client_secret, "AZURE_CLIENT_SECRET", provider)
    elif provider == "aws":
        _require_env(settings.aws_region, "AWS_REGION", provider)
        _require_env(settings.aws_account_id, "AWS_ACCOUNT_ID", provider)
    else:
        _require_env(settings.gcp_project_id, "GCP_PROJECT_ID", provider)

    return settings
