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
    """Public representation of a user (never exposes the password).

    Sprint 18.1A extended this additively — existing consumers keep working,
    and it is the single response model for register and ``GET /auth/me``.
    Secrets (password digest, verification/reset hashes, token epoch) are
    deliberately absent.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    email_verified: bool
    email_verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


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


# --- Sprint 18.1A: logout, verification, password reset ------------------


class LogoutRequest(BaseModel):
    """Payload for logout.

    ``refresh_token`` is accepted for symmetry with clients that hold one, but
    revocation is driven by the authenticated access token, so it is optional.
    """

    refresh_token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    """Payload for requesting a password-reset email."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload for completing a password reset."""

    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=72)


class VerifyEmailRequest(BaseModel):
    """Payload for confirming an email address with a one-time code."""

    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class ResendVerificationRequest(BaseModel):
    """Payload for re-sending the verification code."""

    email: EmailStr


class MessageResponse(BaseModel):
    """Generic, deliberately non-committal acknowledgement.

    Used by the endpoints that must not reveal whether an account exists.
    """

    message: str
