import importlib
import json
from pathlib import Path


def load_spec(cloud: str, lab: str) -> dict:
    spec_path = Path(__file__).parent / "lab_verify" / cloud / lab / "lab_spec.json"
    with open(spec_path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_lab(user: str, email: str, cloud: str, lab: str, subscription_id: str) -> dict:
    module_path = f"lab_verify.{cloud}.{lab}.verify"
    verify_module = importlib.import_module(module_path)

    return verify_module.run_verification(
        user=user,
        lab=lab,
        email=email,
        subscription_id=subscription_id,
    )
