"""
app/schemas/user.py
-------------------
Pydantic schemas for user registration, profile updates, and response serialization.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class UserBase(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="User's unique email address")
    full_name: Optional[str] = Field(default=None, max_length=255, description="Full display name")
    is_active: bool = Field(default=True, description="Account active status")


class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password, minimum 8 characters",
    )


class UserUpdate(BaseModel):
    email: Optional[str] = Field(default=None, pattern=EMAIL_PATTERN)
    full_name: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: str
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
