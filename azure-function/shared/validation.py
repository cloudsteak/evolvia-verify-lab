REQUIRED_FIELDS = ["user", "email", "cloud", "lab"]


def validate_verify_body(body: dict) -> str | None:
    for field in REQUIRED_FIELDS:
        value = body.get(field)
        if value is None or not str(value).strip():
            return f"Hiányzó vagy üres mező: '{field}'."
    return None
