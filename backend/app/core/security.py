"""Security primitives: password hashing (bcrypt) and JWT handling.

This module is intentionally free of business logic and persistence concerns.
It exposes pure functions used by the service layer and dependencies.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]


# --- Password hashing ----------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and return the UTF-8 digest."""
    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``True`` if ``plain_password`` matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        # Malformed/invalid stored hash.
        return False


# --- JWT -----------------------------------------------------------------

def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_access_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    """Create a short-lived access token for ``subject`` (typically a user id)."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(subject, "access", delta)


def create_refresh_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    """Create a long-lived refresh token for ``subject``."""
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(subject, "refresh", delta)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, returning its claims.

    Raises ``jwt.PyJWTError`` (or a subclass) if the token is invalid or
    expired.
    """
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
