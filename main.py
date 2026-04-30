from fastapi import FastAPI, Header, HTTPException

from config import get_settings
from models import VerifyRequest, VerifyResponse
from verify_lab import verify_lab

app = FastAPI(
    title="Evolvia Verify Lab",
    version="0.1.2",
    description="Lab verification microservice for CloudMentor",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info():
    settings = get_settings()
    return {"provider": settings.provider, "version": app.version}


@app.post("/v1/verify", response_model=VerifyResponse)
def verify(
    payload: VerifyRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    settings = get_settings()

    if settings.internal_api_key and x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = verify_lab(
        user=payload.user,
        email=payload.email,
        cloud=payload.cloud,
        lab=payload.lab,
        settings=settings,
    )

    return VerifyResponse(success=result["success"], message=result["message"])
