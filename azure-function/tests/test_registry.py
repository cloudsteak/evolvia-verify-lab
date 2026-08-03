from labs.registry import run_lab


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

    monkeypatch.setattr("labs.registry._LABS", {"basic": fake_verify})
    result = run_lab(lab="basic", user="student1", email="student@example.com")
    assert result["success"] is True
