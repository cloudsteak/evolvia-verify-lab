import importlib
import json
from pathlib import Path

from config import Settings


def load_spec(cloud: str, lab: str) -> dict:
    spec_path = Path(__file__).parent / "checks" / cloud / lab / "lab_spec.json"
    with open(spec_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_provider_config(cloud: str, settings: Settings) -> dict:
    if cloud == "azure":
        return {"subscription_id": settings.azure_subscription_id}
    if cloud == "aws":
        return {"region": settings.aws_region, "account_id": settings.aws_account_id}
    if cloud == "gcp":
        return {"project_id": settings.gcp_project_id}
    raise ValueError(f"Unsupported cloud provider: {cloud}")


def verify_lab(user: str, email: str, cloud: str, lab: str, settings: Settings) -> dict:
    if cloud not in {"azure", "aws", "gcp"}:
        return {
            "success": False,
            "message": f"Nem támogatott felhőszolgáltató: {cloud}.",
        }

    if cloud != settings.provider:
        return {
            "success": False,
            "message": (
                f"A '{cloud}' szolgáltató nem támogatott ebben a környezetben. "
                f"Az aktív szolgáltató: '{settings.provider}'."
            ),
        }

    module_path = f"checks.{cloud}.{lab}.verify"
    verify_module = importlib.import_module(module_path)
    provider_config = _build_provider_config(cloud, settings)

    return verify_module.run_verification(
        user=user,
        lab=lab,
        email=email,
        **provider_config,
    )
