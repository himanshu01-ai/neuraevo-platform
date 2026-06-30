"""Pydantic schemas for user/auth data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Input payload for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)


class UserResponse(BaseModel):
    """Public representation of a user (never exposes the password)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    """Payload for the registration endpoint.

    ``password`` is capped at 72 bytes to align with bcrypt's input limit.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """Payload for the login endpoint."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class RefreshRequest(BaseModel):
    """Payload for exchanging a refresh token for new tokens."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Access + refresh token pair returned by login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
