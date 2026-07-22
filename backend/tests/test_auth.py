"""Authentication tests (Sprint 18.1A).

Three layers, none of which touch a database, network, or SMTP server:

* ``...ServiceTests`` run the real :class:`AuthService` against an in-memory
  fake repository, so token issuance, verification, reset, revocation, expiry,
  and single-use semantics are exercised for real.
* ``AuthAPITests`` drive the endpoints through ``TestClient`` with the service
  mocked, covering HTTP concerns — status codes, error mapping, auth, and
  account-enumeration resistance.
* ``RateLimiterTests`` / ``EmailServiceTests`` / ``SecurityPrimitiveTests``
  cover the supporting pieces directly.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_auth
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.dependencies import (
    get_auth_service,
    get_current_user,
    get_rate_limiter,
)
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
from app.main import app
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import (
    AuthService,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    InvalidTokenError,
    InvalidVerificationCodeError,
)
from app.services.email import EmailDeliveryError, EmailMessage, EmailService
from app.services.email.providers.base import EmailProvider
from app.services.rate_limiter import InMemoryRateLimiter, NullRateLimiter


# --- Test doubles --------------------------------------------------------


class FakeSession:
    """Minimal unit-of-work stand-in that records commits."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, instance) -> None:  # pragma: no cover - no-op
        return None


class FakeUserRepository:
    """In-memory mirror of :class:`UserRepository`'s public surface."""

    def __init__(self, session) -> None:
        self.session = session
        self.users: dict[uuid.UUID, User] = {}
        self.flushes = 0

    # -- reads
    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def get_by_email(self, email):
        return next(
            (u for u in self.users.values() if u.email.lower() == email.lower()), None
        )

    def get_by_password_reset_hash(self, token_hash):
        return next(
            (u for u in self.users.values() if u.password_reset_hash == token_hash),
            None,
        )

    # -- writes
    def create(self, *, email, hashed_password, full_name=None):
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=True,
            email_verified=False,
            token_epoch=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.users[user.id] = user
        return user

    def set_verification_token(self, user, *, token_hash, expires_at):
        user.verification_token_hash = token_hash
        user.verification_expires_at = expires_at
        self.flushes += 1
        return user

    def mark_email_verified(self, user, *, verified_at):
        user.email_verified = True
        user.email_verified_at = verified_at
        user.verification_token_hash = None
        user.verification_expires_at = None
        self.flushes += 1
        return user

    def set_password_reset_token(self, user, *, token_hash, expires_at):
        user.password_reset_hash = token_hash
        user.password_reset_expires_at = expires_at
        self.flushes += 1
        return user

    def set_password(self, user, *, hashed_password):
        user.hashed_password = hashed_password
        user.password_reset_hash = None
        user.password_reset_expires_at = None
        self.flushes += 1
        return user

    def bump_token_epoch(self, user):
        user.token_epoch = (user.token_epoch or 0) + 1
        self.flushes += 1
        return user


class RecordingEmailProvider(EmailProvider):
    """Captures messages instead of delivering them."""

    name = "recording"

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[EmailMessage] = []
        self.fail = fail

    def send(self, message: EmailMessage) -> None:
        if self.fail:
            raise EmailDeliveryError("simulated outage")
        self.sent.append(message)


class AuthServiceTestBase(unittest.TestCase):
    """Builds a real AuthService over the in-memory repository."""

    def setUp(self) -> None:
        self.session = FakeSession()
        self.provider = RecordingEmailProvider()
        self.email_service = EmailService(
            self.provider,
            product_name="NeuraEvo",
            frontend_base_url="https://app.example.com",
        )
        patcher = patch(
            "app.services.auth_service.UserRepository", FakeUserRepository
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = AuthService(self.session, self.email_service)
        self.repo: FakeUserRepository = self.service.users

    def register(self, email="ada@example.com", password="Sprint18secure1"):
        return self.service.register(
            RegisterRequest(email=email, password=password, full_name="Ada Lovelace")
        )

    def latest_code(self) -> str:
        """Pull the code out of the most recent verification email."""
        message = self.provider.sent[-1]
        digits = [w for w in message.text_body.split() if w.isdigit() and len(w) == 6]
        return digits[0]


# --- Registration & login ------------------------------------------------


class RegistrationTests(AuthServiceTestBase):
    def test_register_creates_unverified_user_and_sends_code(self):
        user = self.register()
        self.assertFalse(user.email_verified)
        self.assertIsNone(user.email_verified_at)
        self.assertEqual(len(self.provider.sent), 1)
        self.assertIn("verification code", self.provider.sent[0].subject.lower())

    def test_register_stores_only_the_code_hash(self):
        self.register()
        user = self.repo.get_by_email("ada@example.com")
        code = self.latest_code()
        self.assertIsNotNone(user.verification_token_hash)
        self.assertNotIn(code, user.verification_token_hash)
        self.assertEqual(user.verification_token_hash, hash_secret(code))

    def test_register_never_stores_a_plaintext_password(self):
        user = self.register(password="Sprint18secure1")
        self.assertNotEqual(user.hashed_password, "Sprint18secure1")
        self.assertTrue(verify_password("Sprint18secure1", user.hashed_password))

    def test_duplicate_email_rejected(self):
        self.register()
        with self.assertRaises(EmailAlreadyExistsError):
            self.register()

    def test_email_outage_does_not_fail_registration(self):
        self.provider.fail = True
        user = self.register()
        self.assertIsNotNone(user.id)
        self.assertIsNotNone(user.verification_token_hash)


class LoginTests(AuthServiceTestBase):
    def test_login_issues_token_pair(self):
        self.register()
        tokens = self.service.login(
            LoginRequest(email="ada@example.com", password="Sprint18secure1")
        )
        access = decode_token(tokens.access_token)
        refresh = decode_token(tokens.refresh_token)
        self.assertEqual(access["type"], "access")
        self.assertEqual(refresh["type"], "refresh")
        self.assertEqual(access["sub"], refresh["sub"])

    def test_login_succeeds_before_verification(self):
        """Verification is not a login gate — existing users must not break."""
        self.register()
        tokens = self.service.login(
            LoginRequest(email="ada@example.com", password="Sprint18secure1")
        )
        self.assertTrue(tokens.access_token)

    def test_wrong_password_rejected(self):
        self.register()
        with self.assertRaises(InvalidCredentialsError):
            self.service.login(
                LoginRequest(email="ada@example.com", password="wrongpassword")
            )

    def test_unknown_email_rejected(self):
        with self.assertRaises(InvalidCredentialsError):
            self.service.login(
                LoginRequest(email="nobody@example.com", password="Sprint18secure1")
            )

    def test_inactive_user_rejected(self):
        user = self.register()
        user.is_active = False
        with self.assertRaises(InvalidCredentialsError):
            self.service.login(
                LoginRequest(email="ada@example.com", password="Sprint18secure1")
            )


# --- Refresh, logout, revocation ----------------------------------------


class RefreshAndRevocationTests(AuthServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.register()
        self.tokens = self.service.login(
            LoginRequest(email="ada@example.com", password="Sprint18secure1")
        )

    def test_refresh_returns_a_new_pair(self):
        refreshed = self.service.refresh(self.tokens.refresh_token)
        self.assertTrue(refreshed.access_token)
        self.assertEqual(decode_token(refreshed.refresh_token)["type"], "refresh")

    def test_access_token_rejected_as_refresh_token(self):
        with self.assertRaises(InvalidTokenError):
            self.service.refresh(self.tokens.access_token)

    def test_malformed_refresh_token_rejected(self):
        with self.assertRaises(InvalidTokenError):
            self.service.refresh("not.a.jwt")

    def test_expired_refresh_token_rejected(self):
        # Expired well beyond the JWT clock-skew leeway (Sprint 25), so this still
        # asserts expiry rejection rather than landing inside the skew window.
        expired = create_refresh_token(
            str(self.user.id), expires_delta=timedelta(minutes=-5)
        )
        with self.assertRaises(InvalidTokenError):
            self.service.refresh(expired)

    def test_logout_revokes_the_refresh_token(self):
        self.service.logout(self.user)
        with self.assertRaises(InvalidTokenError):
            self.service.refresh(self.tokens.refresh_token)

    def test_logout_advances_the_token_epoch(self):
        self.assertEqual(self.user.token_epoch, 0)
        self.service.logout(self.user)
        self.assertEqual(self.user.token_epoch, 1)

    def test_logout_invalidates_previously_issued_access_tokens(self):
        claims = decode_token(self.tokens.access_token)
        self.service.logout(self.user)
        self.assertFalse(token_epoch_matches(claims, self.user.token_epoch))

    def test_tokens_issued_after_logout_are_accepted(self):
        self.service.logout(self.user)
        fresh = self.service.login(
            LoginRequest(email="ada@example.com", password="Sprint18secure1")
        )
        self.assertTrue(self.service.refresh(fresh.refresh_token).access_token)

    def test_pre_sprint_tokens_without_epoch_still_validate(self):
        """Backward compatibility: tokens minted before 18.1A carry no ``epc``."""
        claims = {"sub": str(self.user.id), "type": "refresh"}
        self.assertTrue(token_epoch_matches(claims, 0))

    def test_refresh_rejected_for_deactivated_user(self):
        self.user.is_active = False
        with self.assertRaises(InvalidTokenError):
            self.service.refresh(self.tokens.refresh_token)


# --- Email verification --------------------------------------------------


class EmailVerificationTests(AuthServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.register()
        self.code = self.latest_code()

    def test_correct_code_verifies_the_address(self):
        user = self.service.verify_email("ada@example.com", self.code)
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(user.email_verified_at)

    def test_code_is_single_use(self):
        self.service.verify_email("ada@example.com", self.code)
        self.assertIsNone(self.user.verification_token_hash)
        # The consumed code must not work again even if the account were
        # somehow returned to an unverified state.
        self.user.email_verified = False
        with self.assertRaises(InvalidVerificationCodeError):
            self.service.verify_email("ada@example.com", self.code)

    def test_verifying_twice_is_rejected_without_leaking_the_profile(self):
        """The endpoint is unauthenticated, so a wrong/replayed code reveals nothing.

        Answering an already-verified address with its profile would let anyone
        who guessed an email read the account holder's details.
        """
        self.service.verify_email("ada@example.com", self.code)
        with self.assertRaises(InvalidVerificationCodeError):
            self.service.verify_email("ada@example.com", self.code)

    def test_already_verified_account_rejects_any_code(self):
        self.service.verify_email("ada@example.com", self.code)
        with self.assertRaises(InvalidVerificationCodeError):
            self.service.verify_email("ada@example.com", "999999")

    def test_rejection_is_indistinguishable_for_unknown_and_verified(self):
        """Same error either way — no account-enumeration oracle."""
        self.service.verify_email("ada@example.com", self.code)
        with self.assertRaises(InvalidVerificationCodeError) as verified:
            self.service.verify_email("ada@example.com", "999999")
        with self.assertRaises(InvalidVerificationCodeError) as unknown:
            self.service.verify_email("nobody@example.com", "999999")
        self.assertEqual(str(verified.exception), str(unknown.exception))

    def test_wrong_code_rejected(self):
        wrong = "000000" if self.code != "000000" else "111111"
        with self.assertRaises(InvalidVerificationCodeError):
            self.service.verify_email("ada@example.com", wrong)
        self.assertFalse(self.user.email_verified)

    def test_expired_code_rejected(self):
        self.user.verification_expires_at = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        with self.assertRaises(InvalidVerificationCodeError):
            self.service.verify_email("ada@example.com", self.code)

    def test_naive_expiry_timestamp_is_treated_as_utc(self):
        """Databases without timezone support hand back naive datetimes."""
        self.user.verification_expires_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) + timedelta(minutes=5)
        user = self.service.verify_email("ada@example.com", self.code)
        self.assertTrue(user.email_verified)

    def test_unknown_email_rejected_without_disclosure(self):
        with self.assertRaises(InvalidVerificationCodeError):
            self.service.verify_email("nobody@example.com", self.code)

    def test_resend_issues_a_new_code_and_invalidates_the_old_one(self):
        old_hash = self.user.verification_token_hash
        self.service.resend_verification("ada@example.com")
        self.assertNotEqual(self.user.verification_token_hash, old_hash)
        with self.assertRaises(InvalidVerificationCodeError):
            self.service.verify_email("ada@example.com", self.code)
        self.assertTrue(
            self.service.verify_email("ada@example.com", self.latest_code())
        )

    def test_resend_for_unknown_address_is_silent(self):
        self.service.resend_verification("nobody@example.com")
        self.assertEqual(len(self.provider.sent), 1)  # only the registration email

    def test_resend_skipped_for_already_verified_user(self):
        self.service.verify_email("ada@example.com", self.code)
        before = len(self.provider.sent)
        self.service.resend_verification("ada@example.com")
        self.assertEqual(len(self.provider.sent), before)


# --- Password reset ------------------------------------------------------


class PasswordResetTests(AuthServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.register()
        self.provider.sent.clear()

    def reset_token(self) -> str:
        """Extract the token from the reset link in the latest email."""
        return self.provider.sent[-1].text_body.split("token=")[1].split()[0]

    def test_forgot_password_sends_a_reset_link(self):
        self.service.request_password_reset("ada@example.com")
        self.assertEqual(len(self.provider.sent), 1)
        self.assertIn("reset", self.provider.sent[0].subject.lower())
        self.assertIn("https://app.example.com/reset-password?token=",
                      self.provider.sent[0].text_body)

    def test_only_the_token_hash_is_stored(self):
        self.service.request_password_reset("ada@example.com")
        token = self.reset_token()
        self.assertEqual(self.user.password_reset_hash, hash_secret(token))
        self.assertNotIn(token, self.user.password_reset_hash)

    def test_unknown_address_sends_nothing_but_does_not_raise(self):
        self.service.request_password_reset("nobody@example.com")
        self.assertEqual(self.provider.sent, [])

    def test_inactive_user_gets_no_reset_email(self):
        self.user.is_active = False
        self.service.request_password_reset("ada@example.com")
        self.assertEqual(self.provider.sent, [])

    def test_reset_changes_the_password(self):
        self.service.request_password_reset("ada@example.com")
        self.service.reset_password(self.reset_token(), "BrandNewPass9")
        self.assertTrue(verify_password("BrandNewPass9", self.user.hashed_password))
        self.assertFalse(verify_password("Sprint18secure1", self.user.hashed_password))

    def test_reset_token_is_single_use(self):
        self.service.request_password_reset("ada@example.com")
        token = self.reset_token()
        self.service.reset_password(token, "BrandNewPass9")
        with self.assertRaises(InvalidResetTokenError):
            self.service.reset_password(token, "AnotherPass9")

    def test_requesting_again_invalidates_the_previous_token(self):
        self.service.request_password_reset("ada@example.com")
        first = self.reset_token()
        self.service.request_password_reset("ada@example.com")
        with self.assertRaises(InvalidResetTokenError):
            self.service.reset_password(first, "BrandNewPass9")
        self.service.reset_password(self.reset_token(), "BrandNewPass9")

    def test_expired_token_rejected(self):
        self.service.request_password_reset("ada@example.com")
        token = self.reset_token()
        self.user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        with self.assertRaises(InvalidResetTokenError):
            self.service.reset_password(token, "BrandNewPass9")

    def test_unknown_token_rejected(self):
        with self.assertRaises(InvalidResetTokenError):
            self.service.reset_password(generate_reset_token(), "BrandNewPass9")

    def test_reset_revokes_existing_sessions(self):
        tokens = self.service.login(
            LoginRequest(email="ada@example.com", password="Sprint18secure1")
        )
        self.service.request_password_reset("ada@example.com")
        self.service.reset_password(self.reset_token(), "BrandNewPass9")
        with self.assertRaises(InvalidTokenError):
            self.service.refresh(tokens.refresh_token)

    def test_login_works_with_the_new_password(self):
        self.service.request_password_reset("ada@example.com")
        self.service.reset_password(self.reset_token(), "BrandNewPass9")
        tokens = self.service.login(
            LoginRequest(email="ada@example.com", password="BrandNewPass9")
        )
        self.assertTrue(tokens.access_token)


# --- Security primitives -------------------------------------------------


class SecurityPrimitiveTests(unittest.TestCase):
    def test_verification_codes_are_six_digits(self):
        for _ in range(50):
            code = generate_verification_code()
            self.assertEqual(len(code), 6)
            self.assertTrue(code.isdigit())

    def test_verification_codes_vary(self):
        codes = {generate_verification_code() for _ in range(50)}
        self.assertGreater(len(codes), 25)

    def test_reset_tokens_are_long_and_unique(self):
        tokens = {generate_reset_token() for _ in range(50)}
        self.assertEqual(len(tokens), 50)
        self.assertGreaterEqual(len(tokens.pop()), 32)

    def test_hash_secret_is_stable_and_hides_the_secret(self):
        self.assertEqual(hash_secret("abc123"), hash_secret("abc123"))
        self.assertNotIn("abc123", hash_secret("abc123"))
        self.assertNotEqual(hash_secret("abc123"), hash_secret("abc124"))

    def test_verify_secret_matches_only_the_right_secret(self):
        digest = hash_secret("abc123")
        self.assertTrue(verify_secret("abc123", digest))
        self.assertFalse(verify_secret("abc124", digest))

    def test_verify_secret_handles_missing_hash(self):
        self.assertFalse(verify_secret("abc123", None))

    def test_password_hashing_is_salted(self):
        self.assertNotEqual(hash_password("same"), hash_password("same"))
        self.assertTrue(verify_password("same", hash_password("same")))

    def test_token_epoch_embedded_in_issued_tokens(self):
        claims = decode_token(create_access_token("subject", token_epoch=7))
        self.assertEqual(claims["epc"], 7)

    def test_token_epoch_mismatch_detected(self):
        claims = decode_token(create_access_token("subject", token_epoch=1))
        self.assertTrue(token_epoch_matches(claims, 1))
        self.assertFalse(token_epoch_matches(claims, 2))


# --- Rate limiter --------------------------------------------------------


class RateLimiterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.limiter = InMemoryRateLimiter()

    def test_allows_up_to_the_limit(self):
        for _ in range(3):
            self.assertTrue(
                self.limiter.check("k", limit=3, window_seconds=60).allowed
            )

    def test_blocks_past_the_limit(self):
        for _ in range(3):
            self.limiter.check("k", limit=3, window_seconds=60)
        decision = self.limiter.check("k", limit=3, window_seconds=60)
        self.assertFalse(decision.allowed)
        self.assertGreater(decision.retry_after_seconds, 0)

    def test_keys_are_independent(self):
        for _ in range(4):
            self.limiter.check("a", limit=3, window_seconds=60)
        self.assertTrue(self.limiter.check("b", limit=3, window_seconds=60).allowed)

    def test_reset_clears_the_counter(self):
        for _ in range(4):
            self.limiter.check("k", limit=3, window_seconds=60)
        self.limiter.reset("k")
        self.assertTrue(self.limiter.check("k", limit=3, window_seconds=60).allowed)

    def test_window_expiry_starts_a_new_window(self):
        for _ in range(3):
            self.limiter.check("k", limit=3, window_seconds=0)
        self.assertTrue(self.limiter.check("k", limit=3, window_seconds=0).allowed)

    def test_null_limiter_allows_everything(self):
        limiter = NullRateLimiter()
        for _ in range(100):
            self.assertTrue(limiter.check("k", limit=1, window_seconds=60).allowed)


# --- Email service & templates -------------------------------------------


class EmailServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = RecordingEmailProvider()
        self.service = EmailService(
            self.provider,
            product_name="NeuraEvo",
            frontend_base_url="https://app.example.com/",
        )

    def test_verification_email_has_html_and_text_bodies(self):
        self.service.send_verification_email(
            to="ada@example.com", code="123456", expires_minutes=15
        )
        message = self.provider.sent[0]
        self.assertIn("123456", message.html_body)
        self.assertIn("123456", message.text_body)
        self.assertIn("<div", message.html_body)
        self.assertNotIn("<div", message.text_body)
        self.assertIn("15 minutes", message.text_body)

    def test_reset_email_contains_a_usable_link(self):
        self.service.send_password_reset_email(
            to="ada@example.com", token="tok-123", expires_minutes=60
        )
        message = self.provider.sent[0]
        self.assertIn("https://app.example.com/reset-password?token=tok-123",
                      message.text_body)
        self.assertIn("reset-password?token=tok-123", message.html_body)

    def test_reset_url_percent_encodes_the_token(self):
        url = self.service.build_reset_url("a b/c+d")
        self.assertIn("token=a%20b%2Fc%2Bd", url)

    def test_trailing_slash_in_base_url_is_normalised(self):
        self.assertEqual(
            self.service.build_reset_url("t"),
            "https://app.example.com/reset-password?token=t",
        )

    def test_template_escapes_interpolated_values(self):
        service = EmailService(
            self.provider,
            product_name="<script>alert(1)</script>",
            frontend_base_url="https://app.example.com",
        )
        service.send_verification_email(
            to="ada@example.com", code="123456", expires_minutes=15
        )
        self.assertNotIn("<script>", self.provider.sent[0].html_body)

    def test_delivery_failure_propagates(self):
        self.provider.fail = True
        with self.assertRaises(EmailDeliveryError):
            self.service.send_verification_email(
                to="ada@example.com", code="123456", expires_minutes=15
            )

    def test_message_requires_recipient_and_subject(self):
        with self.assertRaises(ValueError):
            EmailMessage(to="", subject="s", html_body="h", text_body="t")
        with self.assertRaises(ValueError):
            EmailMessage(to="a@b.c", subject="", html_body="h", text_body="t")


# --- API layer -----------------------------------------------------------


class AuthAPITests(unittest.TestCase):
    """HTTP concerns with the service mocked out."""

    def setUp(self) -> None:
        self.service = MagicMock(spec=AuthService)
        self.limiter = InMemoryRateLimiter()
        self.user = User(
            id=uuid.uuid4(),
            email="ada@example.com",
            hashed_password="x",
            full_name="Ada Lovelace",
            avatar_url=None,
            is_active=True,
            email_verified=True,
            email_verified_at=datetime.now(timezone.utc),
            token_epoch=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        app.dependency_overrides[get_auth_service] = lambda: self.service
        app.dependency_overrides[get_rate_limiter] = lambda: self.limiter
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def authenticate(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: self.user

    # -- /me
    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_me_returns_the_database_profile(self):
        self.authenticate()
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], str(self.user.id))
        self.assertEqual(body["email"], "ada@example.com")
        self.assertEqual(body["full_name"], "Ada Lovelace")
        self.assertTrue(body["email_verified"])
        self.assertIn("avatar_url", body)
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_me_never_exposes_secrets(self):
        self.authenticate()
        body = self.client.get("/api/v1/auth/me").json()
        for secret in (
            "hashed_password",
            "verification_token_hash",
            "password_reset_hash",
            "token_epoch",
        ):
            self.assertNotIn(secret, body)

    # -- logout
    def test_logout_requires_authentication(self):
        response = self.client.post("/api/v1/auth/logout", json={})
        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_and_returns_204(self):
        self.authenticate()
        response = self.client.post("/api/v1/auth/logout", json={})
        self.assertEqual(response.status_code, 204)
        self.service.logout.assert_called_once_with(self.user)

    def test_logout_accepts_an_optional_refresh_token(self):
        self.authenticate()
        response = self.client.post(
            "/api/v1/auth/logout", json={"refresh_token": "whatever"}
        )
        self.assertEqual(response.status_code, 204)

    # -- forgot password
    def test_forgot_password_returns_generic_ack(self):
        response = self.client.post(
            "/api/v1/auth/forgot-password", json={"email": "ada@example.com"}
        )
        self.assertEqual(response.status_code, 202)
        self.service.request_password_reset.assert_called_once_with("ada@example.com")

    def test_forgot_password_response_is_identical_for_unknown_email(self):
        known = self.client.post(
            "/api/v1/auth/forgot-password", json={"email": "ada@example.com"}
        )
        unknown = self.client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
        )
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json(), unknown.json())

    def test_forgot_password_validates_email_format(self):
        response = self.client.post(
            "/api/v1/auth/forgot-password", json={"email": "not-an-email"}
        )
        self.assertEqual(response.status_code, 422)

    # -- reset password
    def test_reset_password_returns_204(self):
        response = self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": "tok", "new_password": "BrandNewPass9"},
        )
        self.assertEqual(response.status_code, 204)
        self.service.reset_password.assert_called_once_with("tok", "BrandNewPass9")

    def test_reset_password_maps_invalid_token_to_400(self):
        self.service.reset_password.side_effect = InvalidResetTokenError()
        response = self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": "bad", "new_password": "BrandNewPass9"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid or has expired", response.json()["detail"].lower())

    def test_reset_password_enforces_minimum_length(self):
        response = self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": "tok", "new_password": "short"},
        )
        self.assertEqual(response.status_code, 422)

    # -- verify email
    def test_verify_email_returns_the_updated_user(self):
        self.service.verify_email.return_value = self.user
        response = self.client.post(
            "/api/v1/auth/verify-email",
            json={"email": "ada@example.com", "code": "123456"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["email_verified"])

    def test_verify_email_maps_invalid_code_to_400(self):
        self.service.verify_email.side_effect = InvalidVerificationCodeError()
        response = self.client.post(
            "/api/v1/auth/verify-email",
            json={"email": "ada@example.com", "code": "000000"},
        )
        self.assertEqual(response.status_code, 400)

    # -- resend verification
    def test_resend_verification_returns_generic_ack(self):
        response = self.client.post(
            "/api/v1/auth/resend-verification", json={"email": "ada@example.com"}
        )
        self.assertEqual(response.status_code, 202)
        self.service.resend_verification.assert_called_once_with("ada@example.com")

    def test_resend_response_is_identical_for_unknown_email(self):
        known = self.client.post(
            "/api/v1/auth/resend-verification", json={"email": "ada@example.com"}
        )
        unknown = self.client.post(
            "/api/v1/auth/resend-verification", json={"email": "nobody@example.com"}
        )
        self.assertEqual(known.json(), unknown.json())

    # -- existing contracts still hold
    def test_login_maps_invalid_credentials_to_401(self):
        self.service.login.side_effect = InvalidCredentialsError()
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 401)

    def test_register_maps_duplicate_to_409(self):
        self.service.register.side_effect = EmailAlreadyExistsError()
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "ada@example.com", "password": "Sprint18secure1"},
        )
        self.assertEqual(response.status_code, 409)

    def test_register_returns_the_extended_user_shape(self):
        self.service.register.return_value = self.user
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "ada@example.com", "password": "Sprint18secure1"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("email_verified", response.json())

    def test_refresh_maps_invalid_token_to_401(self):
        self.service.refresh.side_effect = InvalidTokenError()
        response = self.client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "bad"}
        )
        self.assertEqual(response.status_code, 401)


class RateLimitedEndpointTests(unittest.TestCase):
    """The limiter is wired into the sensitive endpoints."""

    def setUp(self) -> None:
        self.service = MagicMock(spec=AuthService)
        self.limiter = InMemoryRateLimiter()
        app.dependency_overrides[get_auth_service] = lambda: self.service
        app.dependency_overrides[get_rate_limiter] = lambda: self.limiter
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_repeated_failed_logins_are_throttled(self):
        self.service.login.side_effect = InvalidCredentialsError()
        payload = {"email": "ada@example.com", "password": "wrongpassword"}
        statuses = [
            self.client.post("/api/v1/auth/login", json=payload).status_code
            for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS + 1)
        ]
        self.assertEqual(statuses[0], 401)
        self.assertEqual(statuses[-1], 429)

    def test_throttled_response_carries_retry_after(self):
        self.service.login.side_effect = InvalidCredentialsError()
        payload = {"email": "ada@example.com", "password": "wrongpassword"}
        response = None
        for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS + 1):
            response = self.client.post("/api/v1/auth/login", json=payload)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_successful_login_clears_the_counter(self):
        payload = {"email": "ada@example.com", "password": "Sprint18secure1"}
        self.service.login.side_effect = InvalidCredentialsError()
        for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS - 1):
            self.client.post("/api/v1/auth/login", json=payload)

        self.service.login.side_effect = None
        self.service.login.return_value = MagicMock(
            access_token="a", refresh_token="r", token_type="bearer"
        )
        self.assertEqual(
            self.client.post("/api/v1/auth/login", json=payload).status_code, 200
        )

        # Counter reset -> a fresh run of failures is allowed again.
        self.service.login.side_effect = InvalidCredentialsError()
        self.assertEqual(
            self.client.post("/api/v1/auth/login", json=payload).status_code, 401
        )

    def test_verification_resend_is_throttled(self):
        payload = {"email": "ada@example.com"}
        statuses = [
            self.client.post(
                "/api/v1/auth/resend-verification", json=payload
            ).status_code
            for _ in range(settings.EMAIL_SEND_RATE_LIMIT_ATTEMPTS + 1)
        ]
        self.assertEqual(statuses[-1], 429)

    def test_forgot_password_is_throttled(self):
        payload = {"email": "ada@example.com"}
        statuses = [
            self.client.post("/api/v1/auth/forgot-password", json=payload).status_code
            for _ in range(settings.EMAIL_SEND_RATE_LIMIT_ATTEMPTS + 1)
        ]
        self.assertEqual(statuses[-1], 429)

    def test_verify_email_is_throttled(self):
        self.service.verify_email.side_effect = InvalidVerificationCodeError()
        payload = {"email": "ada@example.com", "code": "000000"}
        statuses = [
            self.client.post("/api/v1/auth/verify-email", json=payload).status_code
            for _ in range(settings.VERIFY_RATE_LIMIT_ATTEMPTS + 1)
        ]
        self.assertEqual(statuses[-1], 429)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
