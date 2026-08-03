import json

import azure.functions as func
from function_app import dispatcher, health


def _request(method: str, url: str, body: bytes | None = None) -> func.HttpRequest:
    return func.HttpRequest(
        method=method,
        url=url,
        headers={},
        params={},
        body=body,
    )


def test_health_returns_ok():
    response = health(_request("GET", "/api/health"))
    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"status": "ok"}


def test_dispatcher_rejects_invalid_json():
    response = dispatcher(_request("POST", "/api/dispatcher", body=b"not-json"))
    assert response.status_code == 400
    assert "Érvénytelen JSON" in json.loads(response.get_body())["message"]


def test_dispatcher_rejects_non_azure_cloud():
    body = json.dumps(
        {
            "user": "student1",
            "email": "student@example.com",
            "cloud": "aws",
            "lab": "basic",
        }
    ).encode()
    response = dispatcher(_request("POST", "/api/dispatcher", body=body))
    assert response.status_code == 400
    payload = json.loads(response.get_body())
    assert payload["success"] is False
    assert "azure" in payload["message"]
