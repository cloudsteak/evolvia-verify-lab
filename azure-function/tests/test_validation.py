import pytest
from shared.validation import validate_verify_body


def test_validate_verify_body_ok():
    assert (
        validate_verify_body(
            {
                "user": "student1",
                "email": "student@example.com",
                "cloud": "azure",
                "lab": "basic",
            }
        )
        is None
    )


@pytest.mark.parametrize("field", ["user", "email", "cloud", "lab"])
def test_validate_verify_body_missing_field(field):
    payload = {
        "user": "student1",
        "email": "student@example.com",
        "cloud": "azure",
        "lab": "basic",
    }
    payload[field] = "   "
    assert validate_verify_body(payload) == f"Hiányzó vagy üres mező: '{field}'."
