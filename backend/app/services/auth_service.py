"""Authentication service: registration, login, and token lifecycle.

Holds the business logic that sits between the API layer and the repository
layer. Raises domain-specific exceptions which the API layer translates into
HTTP responses.
"""

import uuid

import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuthError(Exception):
    """Base class for authentication-related errors."""


class EmailAlreadyExistsError(AuthError):
    """Raised when registering with an email that is already taken."""


class InvalidCredentialsError(AuthError):
    """Raised when login credentials do not match an active user."""


class InvalidTokenError(AuthError):
    """Raised when a token is missing, malformed, expired, or the wrong type."""


class AuthService:
    """Coordinates user authentication using the repository layer.

    The service owns the unit of work: repositories ``flush`` while the service
    is responsible for committing the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.users = UserRepository(session)

    # --- Registration ----------------------------------------------------

    def register(self, data: RegisterRequest) -> User:
        """Create a new user, enforcing email uniqueness."""
        if self.users.get_by_email(data.email) is not None:
            raise EmailAlreadyExistsError(data.email)

        user = self.users.create(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        self.session.commit()
        self.session.refresh(user)
        logger.info("Registered new user %s", user.id)
        return user

    # --- Login -----------------------------------------------------------

    def authenticate(self, email: str, password: str) -> User:
        """Return the user if credentials are valid and the account is active."""
        user = self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        if not user.is_active:
            raise InvalidCredentialsError()
        return user

    def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate and issue a fresh access/refresh token pair."""
        user = self.authenticate(data.email, data.password)
        return self._issue_tokens(user)

    # --- Tokens ----------------------------------------------------------

    def _issue_tokens(self, user: User) -> TokenResponse:
        subject = str(user.id)
        return TokenResponse(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
        )

    def refresh(self, refresh_token: str) -> TokenResponse:
        """Validate a refresh token and issue a new token pair."""
        try:
            claims = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("Invalid or expired refresh token") from exc

        if claims.get("type") != "refresh":
            raise InvalidTokenError("Expected a refresh token")

        user = self._user_from_subject(claims.get("sub"))
        if user is None or not user.is_active:
            raise InvalidTokenError("User no longer valid")

        return self._issue_tokens(user)

    # --- Helpers ---------------------------------------------------------

    def _user_from_subject(self, subject: str | None) -> User | None:
        if not subject:
            return None
        try:
            user_id = uuid.UUID(subject)
        except ValueError:
            return None
        return self.users.get_by_id(user_id)
