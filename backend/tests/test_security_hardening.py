"""Security hardening tests (Sprint 25).

Prove the additive security controls without touching any domain: security
response headers (consistent, configurable, HSTS gated to production+HTTPS), the
CORS production guard, the request body-size limit, per-user AI rate limiting,
JWT clock-skew leeway, and the absence of secret/token leakage in logs and
errors. Everything keeps the platform's one ``{"detail": ...}`` error contract.

    PYTHONPATH=. python -m unittest tests.test_security_hardening
"""

import logging
import unittest
from datetime import timedelta
from types import SimpleNamespace

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.rate_limit import enforce_ai_rate_limit, get_ai_rate_limiter
from app.core.config import Settings, settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, decode_token
from app.main import app
from app.services.rate_limiter import InMemoryRateLimiter


class SecurityHeadersTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_headers_present_on_success(self):
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(r.headers.get("Referrer-Policy"), settings.SECURITY_REFERRER_POLICY)
        self.assertTrue(r.headers.get("Content-Security-Policy"))
        self.assertTrue(r.headers.get("Permissions-Policy"))

    def test_headers_present_on_errors_too(self):
        # Applied consistently — an error response is hardened just like a 200.
        for path, expected in (("/api/v1/nope", 404), ("/api/v1/tasks", 401)):
            r = self.client.get(path)
            self.assertEqual(r.status_code, expected)
            self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertTrue(r.headers.get("Content-Security-Policy"))

    def test_csp_is_configurable(self):
        original = settings.SECURITY_CSP
        settings.SECURITY_CSP = "default-src 'self'"
        try:
            r = self.client.get("/api/v1/health")
            self.assertEqual(r.headers.get("Content-Security-Policy"), "default-src 'self'")
        finally:
            settings.SECURITY_CSP = original

    def test_hsts_absent_in_development(self):
        r = self.client.get("/api/v1/health", headers={"X-Forwarded-Proto": "https"})
        self.assertIsNone(r.headers.get("Strict-Transport-Security"))

    def test_hsts_present_in_production_over_https_only(self):
        original = settings.ENVIRONMENT
        settings.ENVIRONMENT = "production"
        try:
            # Over HTTPS → HSTS present.
            r = self.client.get("/api/v1/health", headers={"X-Forwarded-Proto": "https"})
            self.assertIn("max-age=", r.headers.get("Strict-Transport-Security", ""))
            # Over plain HTTP → never pinned.
            r2 = self.client.get("/api/v1/health", headers={"X-Forwarded-Proto": "http"})
            self.assertIsNone(r2.headers.get("Strict-Transport-Security"))
        finally:
            settings.ENVIRONMENT = original


class CorsGuardTests(unittest.TestCase):
    def test_wildcard_refused_in_production(self):
        with self.assertRaises(ValueError):
            Settings(
                ENVIRONMENT="production",
                CORS_ORIGINS=["*"],
                JWT_SECRET_KEY="prod-secret-not-the-dev-default",
            )

    def test_explicit_origins_allowed_in_production(self):
        s = Settings(
            ENVIRONMENT="production",
            CORS_ORIGINS=["https://app.neuraevo.com"],
            JWT_SECRET_KEY="prod-secret-not-the-dev-default",
        )
        self.assertTrue(s.is_production)

    def test_wildcard_allowed_in_development(self):
        s = Settings(ENVIRONMENT="development", CORS_ORIGINS=["*"])
        self.assertFalse(s.is_production)

    def test_credentials_not_enabled_with_wildcard_origin(self):
        # With the permissive dev wildcard, credentialed CORS must be off.
        client = TestClient(app)
        r = client.get("/api/v1/health", headers={"Origin": "http://example.com"})
        self.assertNotEqual(r.headers.get("Access-Control-Allow-Credentials"), "true")


class BodySizeLimitTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_oversized_body_is_413_json(self):
        over = settings.MAX_REQUEST_BODY_BYTES + 1
        r = self.client.post(
            "/api/v1/auth/login",
            content=b"{}",
            headers={"Content-Length": str(over), "Content-Type": "application/json"},
        )
        self.assertEqual(r.status_code, 413)
        self.assertIn("detail", r.json())
        self.assertTrue(r.headers.get("X-Request-ID"))

    def test_normal_body_passes_the_limit(self):
        # A small, well-formed request is not blocked by the limit (it 422s on
        # validation instead, which proves it reached the app).
        r = self.client.post("/api/v1/auth/login", json={})
        self.assertNotEqual(r.status_code, 413)


class AiRateLimitTests(unittest.TestCase):
    """The per-user AI limiter, exercised in isolation via a mini app."""

    def setUp(self):
        self.mini = FastAPI()

        @self.mini.get("/ai", dependencies=[Depends(enforce_ai_rate_limit)])
        def ai_endpoint():
            return {"ok": True}

        self.limiter = InMemoryRateLimiter()
        self.mini.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
        self.mini.dependency_overrides[get_ai_rate_limiter] = lambda: self.limiter
        self.client = TestClient(self.mini)

        self._orig_attempts = settings.AI_RATE_LIMIT_ATTEMPTS
        settings.AI_RATE_LIMIT_ATTEMPTS = 2

    def tearDown(self):
        settings.AI_RATE_LIMIT_ATTEMPTS = self._orig_attempts

    def test_limit_then_429_with_detail_and_retry_after(self):
        self.assertEqual(self.client.get("/ai").status_code, 200)
        self.assertEqual(self.client.get("/ai").status_code, 200)
        r = self.client.get("/ai")
        self.assertEqual(r.status_code, 429)
        self.assertIn("detail", r.json())  # the {detail} contract
        self.assertTrue(r.headers.get("Retry-After"))

    def test_separate_users_have_separate_budgets(self):
        # A second user is unaffected by the first's exhausted budget.
        self.client.get("/ai")
        self.client.get("/ai")
        self.mini.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-2")
        self.assertEqual(self.client.get("/ai").status_code, 200)


class JwtLeewayTests(unittest.TestCase):
    def test_token_within_leeway_is_accepted(self):
        # Expired a few seconds ago but inside the skew window → still valid.
        token = create_access_token("user-1", expires_delta=timedelta(seconds=-5))
        claims = decode_token(token)
        self.assertEqual(claims["sub"], "user-1")

    def test_token_beyond_leeway_is_rejected(self):
        token = create_access_token(
            "user-1",
            expires_delta=timedelta(seconds=-(settings.JWT_LEEWAY_SECONDS + 120)),
        )
        with self.assertRaises(jwt.ExpiredSignatureError):
            decode_token(token)

    def test_algorithm_is_pinned(self):
        # A token signed with an unexpected algorithm is rejected (no confusion).
        forged = jwt.encode({"sub": "x"}, "other-secret", algorithm="HS512")
        with self.assertRaises(jwt.PyJWTError):
            decode_token(forged)


class LeakageTests(unittest.TestCase):
    def test_authorization_header_is_never_logged(self):
        client = TestClient(app, raise_server_exceptions=False)
        with self.assertLogs("app.access", level="INFO") as captured:
            client.get(
                "/api/v1/tasks",
                headers={"Authorization": "Bearer super-secret-token-value"},
            )
        blob = "\n".join(captured.output)
        self.assertNotIn("super-secret-token-value", blob)
        self.assertNotIn("Bearer", blob)

    def test_500_does_not_leak_exception_internals(self):
        from app.main import create_app

        fresh = create_app()

        @fresh.get("/api/v1/_leak")
        def _leak():
            raise RuntimeError("token=abc secret_key=xyz")

        r = TestClient(fresh, raise_server_exceptions=False).get("/api/v1/_leak")
        self.assertEqual(r.status_code, 500)
        body = str(r.json())
        self.assertNotIn("abc", body)
        self.assertNotIn("xyz", body)


if __name__ == "__main__":
    unittest.main()
