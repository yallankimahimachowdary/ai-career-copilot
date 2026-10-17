"""
app/schemas/auth.py
-------------------
Pydantic schemas for authentication requests and JWT token responses.
"""

from typing import Optional
from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class LoginRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="Registered account email")
    password: str = Field(..., description="Account password")


class Token(BaseModel):
    access_token: str = Field(..., description="Signed JWT Bearer token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in_seconds: int = Field(..., description="Access token lifetime in seconds")


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
