import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    azure_subscription_id: str
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    internal_api_key: str | None = None


def get_settings() -> Settings:
    return Settings(
        azure_subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
        azure_tenant_id=os.environ["AZURE_TENANT_ID"],
        azure_client_id=os.environ["AZURE_CLIENT_ID"],
        azure_client_secret=os.environ["AZURE_CLIENT_SECRET"],
        internal_api_key=os.getenv("INTERNAL_VERIFY_API_KEY"),
    )
