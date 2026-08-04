from pathlib import Path

import pytest
from labs.registry import _load_handler, run_lab

REPO_ROOT = Path(__file__).resolve().parents[2]
AZURE_CHECKS = REPO_ROOT / "checks" / "azure"


def _azure_lab_names() -> list[str]:
    return sorted(
        path.name
        for path in AZURE_CHECKS.iterdir()
        if path.is_dir() and (path / "verify.py").is_file()
    )


@pytest.mark.parametrize("lab_name", _azure_lab_names())
def test_load_handler_for_each_azure_lab(lab_name):
    assert _load_handler(lab_name) is not None


def test_load_handler_rejects_invalid_lab_names():
    assert _load_handler("../basic") is None
    assert _load_handler("foo.bar") is None
    assert _load_handler("") is None


def test_run_lab_unknown():
    result = run_lab(lab="unknown", user="student1", email="student@example.com")
    assert result == {"success": False, "message": "Ismeretlen lab: 'unknown'."}


def test_run_lab_missing_subscription_id(monkeypatch):
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    result = run_lab(lab="basic", user="student1", email="student@example.com")
    assert result["success"] is False
    assert "AZURE_SUBSCRIPTION_ID" in result["message"]


def test_run_lab_basic_delegates(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000001")

    def fake_verify(**kwargs):
        assert kwargs["user"] == "student1"
        assert kwargs["lab"] == "basic"
        assert kwargs["email"] == "student@example.com"
        assert kwargs["subscription_id"] == "00000000-0000-0000-0000-000000000001"
        return {"success": True, "message": "Lab sikeresen ellenőrizve."}

    monkeypatch.setattr("labs.registry._load_handler", lambda lab: fake_verify if lab == "basic" else None)
    result = run_lab(lab="basic", user="student1", email="student@example.com")
    assert result["success"] is True
