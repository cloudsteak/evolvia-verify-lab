from pydantic import BaseModel, EmailStr


class VerifyRequest(BaseModel):
    user: str
    email: EmailStr
    cloud: str
    lab: str


class VerifyResponse(BaseModel):
    success: bool
    message: str
