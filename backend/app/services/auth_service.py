"""Authentication service: registration, login, and token lifecycle.

Holds the business logic that sits between the API layer and the repository
layer. Raises domain-specific exceptions which the API layer translates into
HTTP responses.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_token,
    generate_verification_code,
    hash_password,
    hash_secret,
    token_epoch_matches,
    verify_password,
    verify_secret,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.email import EmailDeliveryError, EmailService
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


class InvalidVerificationCodeError(AuthError):
    """Raised when an email-verification code is wrong, expired, or used."""


class InvalidResetTokenError(AuthError):
    """Raised when a password-reset token is wrong, expired, or used."""


class AuthService:
    """Coordinates user authentication using the repository layer.

    The service owns the unit of work: repositories ``flush`` while the service
    is responsible for committing the transaction.
    """

    def __init__(self, session, email_service: Optional[EmailService] = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        # Injected from the composition root. Optional so existing two-argument
        # construction (and tests that never send email) keep working; the
        # email-dependent flows degrade to "issued but not delivered".
        self.email_service = email_service

    # --- Registration ----------------------------------------------------

    def register(self, data: RegisterRequest) -> User:
        """Create a new user, enforcing email uniqueness.

        Issues a verification code and emails it. Delivery problems are logged
        but never fail the registration — the account exists, and the user can
        request a new code from the resend endpoint.
        """
        if self.users.get_by_email(data.email) is not None:
            raise EmailAlreadyExistsError(data.email)

        user = self.users.create(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        code = self._issue_verification_code(user)
        self.session.commit()
        self.session.refresh(user)
        logger.info("Registered new user %s", user.id)

        self._deliver_verification_code(user, code)
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
        epoch = user.token_epoch or 0
        return TokenResponse(
            access_token=create_access_token(subject, token_epoch=epoch),
            refresh_token=create_refresh_token(subject, token_epoch=epoch),
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

        # Revoked by a logout or password reset that happened after this token
        # was minted.
        if not token_epoch_matches(claims, user.token_epoch or 0):
            raise InvalidTokenError("Token has been revoked")

        return self._issue_tokens(user)

    # --- Logout ----------------------------------------------------------

    def logout(self, user: User) -> None:
        """Revoke every token previously issued to ``user``.

        Advancing the user's ``token_epoch`` invalidates their outstanding
        access *and* refresh tokens at once: ``get_current_user`` already loads
        the user on every authenticated request, so the epoch check costs no
        extra query and takes effect immediately.
        """
        self.users.bump_token_epoch(user)
        self.session.commit()
        logger.info("Logged out user %s (token epoch %s)", user.id, user.token_epoch)

    # --- Email verification ----------------------------------------------

    def _issue_verification_code(self, user: User) -> str:
        """Generate, hash, and store a fresh verification code.

        Returns the plaintext code for delivery; only its digest is persisted,
        and issuing a new code invalidates any previous one.
        """
        code = generate_verification_code()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.EMAIL_VERIFICATION_CODE_TTL_MINUTES
        )
        self.users.set_verification_token(
            user, token_hash=hash_secret(code), expires_at=expires_at
        )
        return code

    def _deliver_verification_code(self, user: User, code: str) -> None:
        if self.email_service is None:
            logger.warning(
                "No email service configured; verification code for %s not sent",
                user.id,
            )
            return
        try:
            self.email_service.send_verification_email(
                to=user.email,
                code=code,
                expires_minutes=settings.EMAIL_VERIFICATION_CODE_TTL_MINUTES,
            )
        except EmailDeliveryError:
            logger.warning("Verification email to user %s failed to send", user.id)

    def verify_email(self, email: str, code: str) -> User:
        """Confirm an address with its one-time code.

        The code is single-use and time-limited, and the endpoint is
        unauthenticated — the code itself is the proof of mailbox control. Every
        rejection therefore raises the *same* error, whether the address is
        unknown, already verified, expired, or the code is simply wrong.

        Answering an already-verified address with its profile would have been
        friendlier for a double submit, but this endpoint needs no credentials:
        that would have let anyone who guessed an email address read the account
        holder's profile and distinguish registered addresses from unregistered
        ones. Correctness of the code is the only thing that unlocks a response.
        """
        user = self.users.get_by_email(email)
        if user is None:
            raise InvalidVerificationCodeError("Invalid or expired code")

        if user.email_verified:
            raise InvalidVerificationCodeError("Invalid or expired code")

        if not self._token_is_current(user.verification_expires_at):
            raise InvalidVerificationCodeError("Invalid or expired code")

        if not verify_secret(code, user.verification_token_hash):
            raise InvalidVerificationCodeError("Invalid or expired code")

        self.users.mark_email_verified(user, verified_at=datetime.now(timezone.utc))
        self.session.commit()
        self.session.refresh(user)
        logger.info("Verified email for user %s", user.id)
        return user

    def resend_verification(self, email: str) -> None:
        """Re-issue a verification code.

        Returns nothing regardless of outcome: the caller responds identically
        whether or not the address exists, so this cannot be used to enumerate
        accounts.
        """
        user = self.users.get_by_email(email)
        if user is None or not user.is_active or user.email_verified:
            logger.info("Resend verification ignored for %s", email)
            return

        code = self._issue_verification_code(user)
        self.session.commit()
        self._deliver_verification_code(user, code)

    # --- Password reset ---------------------------------------------------

    def request_password_reset(self, email: str) -> None:
        """Issue and email a single-use reset token.

        Returns nothing regardless of outcome — see :meth:`resend_verification`
        for why. Issuing a new token invalidates any outstanding one.
        """
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            logger.info("Password reset requested for unknown address %s", email)
            return

        token = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES
        )
        self.users.set_password_reset_token(
            user, token_hash=hash_secret(token), expires_at=expires_at
        )
        self.session.commit()

        if self.email_service is None:
            logger.warning(
                "No email service configured; reset token for %s not sent", user.id
            )
            return
        try:
            self.email_service.send_password_reset_email(
                to=user.email,
                token=token,
                expires_minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES,
            )
        except EmailDeliveryError:
            logger.warning("Password reset email to user %s failed to send", user.id)

    def reset_password(self, token: str, new_password: str) -> User:
        """Consume a reset token and set a new password.

        On success the token is consumed, the new password is hashed, and every
        previously issued session token is revoked — a password reset must not
        leave an attacker's existing session alive.
        """
        user = self.users.get_by_password_reset_hash(hash_secret(token))
        if user is None or not user.is_active:
            raise InvalidResetTokenError("Invalid or expired reset token")

        if not self._token_is_current(user.password_reset_expires_at):
            raise InvalidResetTokenError("Invalid or expired reset token")

        self.users.set_password(user, hashed_password=hash_password(new_password))
        self.users.bump_token_epoch(user)
        self.session.commit()
        self.session.refresh(user)
        logger.info("Password reset completed for user %s", user.id)
        return user

    # --- Helpers ---------------------------------------------------------

    @staticmethod
    def _token_is_current(expires_at: Optional[datetime]) -> bool:
        """Return ``True`` when a one-time secret exists and has not expired.

        Stored timestamps may come back naive from databases without timezone
        support, so a naive value is interpreted as UTC rather than compared
        against an aware ``now`` (which would raise).
        """
        if expires_at is None:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > datetime.now(timezone.utc)

    def _user_from_subject(self, subject: str | None) -> User | None:
        if not subject:
            return None
        try:
            user_id = uuid.UUID(subject)
        except ValueError:
            return None
        return self.users.get_by_id(user_id)
