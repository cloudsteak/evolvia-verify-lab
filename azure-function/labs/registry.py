import importlib
import os
import re
from collections.abc import Callable

LabHandler = Callable[..., dict]

_LAB_NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")


def _load_handler(lab: str) -> LabHandler | None:
    if not _LAB_NAME_PATTERN.match(lab):
        return None

    try:
        module = importlib.import_module(f"checks.azure.{lab}.verify")
    except ModuleNotFoundError:
        return None

    run_verification = getattr(module, "run_verification", None)
    if not callable(run_verification):
        return None

    return run_verification


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
