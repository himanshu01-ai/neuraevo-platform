"""Security primitives: password hashing (bcrypt) and JWT handling.

This module is intentionally free of business logic and persistence concerns.
It exposes pure functions used by the service layer and dependencies.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# Number of digits in an email-verification code. Six keeps the existing
# one-time-code UI unchanged; the low entropy is compensated for by a short
# TTL, single use, and rate limiting on the verify endpoint.
VERIFICATION_CODE_DIGITS = 6


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
    token_epoch: int = 0,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        # Revocation marker (Sprint 18.1A): tokens are rejected once the
        # user's stored ``token_epoch`` moves past the value they were minted
        # with. See ``token_epoch_matches``.
        "epc": token_epoch,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    token_epoch: int = 0,
) -> str:
    """Create a short-lived access token for ``subject`` (typically a user id)."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(subject, "access", delta, token_epoch)


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
    token_epoch: int = 0,
) -> str:
    """Create a long-lived refresh token for ``subject``."""
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(subject, "refresh", delta, token_epoch)


def token_epoch_matches(claims: dict[str, Any], token_epoch: int) -> bool:
    """Return ``True`` when a token's revocation marker is still current.

    Tokens minted before Sprint 18.1A carry no ``epc`` claim; they are treated
    as epoch ``0`` so previously issued tokens keep working for users who have
    never logged out or reset their password (whose stored epoch is also ``0``).
    """
    return int(claims.get("epc", 0)) == token_epoch


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, returning its claims.

    The algorithm is pinned to the configured one (so ``alg=none`` and
    algorithm-confusion are rejected), and a small ``leeway`` (Sprint 25) absorbs
    minor clock skew between the signing and validating hosts so a just-issued
    token is not spuriously rejected.

    Raises ``jwt.PyJWTError`` (or a subclass) if the token is invalid or
    expired.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        leeway=settings.JWT_LEEWAY_SECONDS,
    )


# --- One-time secrets (email verification / password reset) --------------
#
# Shared by both flows so token generation, hashing, and comparison exist in
# exactly one place. Secrets are stored only as SHA-256 hashes: they are
# high-entropy (or short-lived and rate-limited) random values, so a fast
# digest is the right primitive here — bcrypt is for low-entropy user
# passwords and would add latency without adding security.


def generate_verification_code() -> str:
    """Return a cryptographically random numeric email-verification code."""
    upper_bound = 10**VERIFICATION_CODE_DIGITS
    return str(secrets.randbelow(upper_bound)).zfill(VERIFICATION_CODE_DIGITS)


def generate_reset_token() -> str:
    """Return a cryptographically random, URL-safe password-reset token."""
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    """Return the SHA-256 hex digest used to persist a one-time secret."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(secret: str, hashed_secret: str | None) -> bool:
    """Constant-time comparison of a presented secret against its stored hash."""
    if not hashed_secret:
        return False
    return hmac.compare_digest(hash_secret(secret), hashed_secret)
