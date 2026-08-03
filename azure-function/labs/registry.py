import os
from collections.abc import Callable

LabHandler = Callable[..., dict]


def _load_handler(lab: str) -> LabHandler | None:
    if lab == "basic":
        from checks.azure.basic.verify import run_verification

        return run_verification
    return None


def run_lab(lab: str, user: str, email: str) -> dict:
    normalized = lab.strip().lower()
    handler = _load_handler(normalized)
    if handler is None:
        return {"success": False, "message": f"Ismeretlen lab: '{lab}'."}

    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        return {
            "success": False,
            "message": "Hiányzó AZURE_SUBSCRIPTION_ID környezeti változó.",
        }

    return handler(
        user=user.strip(),
        lab=normalized,
        email=email.strip(),
        subscription_id=subscription_id,
    )
