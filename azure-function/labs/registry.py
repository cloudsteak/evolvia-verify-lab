import os
from collections.abc import Callable

from checks.azure.basic.verify import run_verification as basic_verify

LabHandler = Callable[..., dict]

_LABS: dict[str, LabHandler] = {
    "basic": basic_verify,
}


def run_lab(lab: str, user: str, email: str) -> dict:
    handler = _LABS.get(lab.strip().lower())
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
        lab=lab.strip().lower(),
        email=email.strip(),
        subscription_id=subscription_id,
    )
