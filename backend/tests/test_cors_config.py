"""H2 production-hardening tests — CORS configuration safety.

Verifies the Sprint 12.15 HIGH finding is resolved: outside development the
application refuses to start with an insecure CORS configuration (wildcard
origin, or empty origin list), while development keeps the convenient wildcard
default. Mirrors the JWT production-safety validation.

Settings are constructed directly with ``_env_file=None`` so the local ``.env``
never influences the assertions; a valid non-default ``JWT_SECRET_KEY`` is
supplied for production cases so the (separate) JWT validator never masks the
CORS assertion under test.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_cors_config
"""

import unittest

from pydantic import ValidationError

from app.core.config import Settings

_PROD_SECRET = "a-strong-production-secret-key-value"


def _settings(**overrides):
    """Build Settings isolated from the local .env, JWT-safe by default."""
    payload = {"_env_file": None, "JWT_SECRET_KEY": _PROD_SECRET}
    payload.update(overrides)
    return Settings(**payload)


class DevelopmentCorsTests(unittest.TestCase):
    def test_default_development_allows_wildcard(self):
        settings = _settings(ENVIRONMENT="development")
        self.assertEqual(settings.CORS_ORIGINS, ["*"])

    def test_development_wildcard_explicitly_allowed(self):
        settings = _settings(ENVIRONMENT="development", CORS_ORIGINS=["*"])
        self.assertEqual(settings.CORS_ORIGINS, ["*"])

    def test_development_default_secret_still_allowed(self):
        # Development convenience is fully preserved (no JWT override needed).
        settings = Settings(_env_file=None, ENVIRONMENT="development")
        self.assertEqual(settings.CORS_ORIGINS, ["*"])


class ProductionCorsFailFastTests(unittest.TestCase):
    def test_production_wildcard_fails_fast(self):
        with self.assertRaises(ValidationError) as ctx:
            _settings(ENVIRONMENT="production", CORS_ORIGINS=["*"])
        self.assertIn("CORS_ORIGINS", str(ctx.exception))

    def test_production_wildcard_among_explicit_origins_fails(self):
        with self.assertRaises(ValidationError):
            _settings(
                ENVIRONMENT="production",
                CORS_ORIGINS=["https://app.neuraevo.com", "*"],
            )

    def test_production_empty_origins_fails_fast(self):
        with self.assertRaises(ValidationError) as ctx:
            _settings(ENVIRONMENT="production", CORS_ORIGINS=[])
        self.assertIn("CORS_ORIGINS", str(ctx.exception))

    def test_non_development_environments_are_all_enforced(self):
        for env in ("production", "staging", "PRODUCTION", "Staging", "prod"):
            with self.assertRaises(ValidationError, msg=env):
                _settings(ENVIRONMENT=env, CORS_ORIGINS=["*"])


class ProductionCorsSuccessTests(unittest.TestCase):
    def test_production_explicit_origin_ok(self):
        settings = _settings(
            ENVIRONMENT="production",
            CORS_ORIGINS=["https://app.neuraevo.com"],
        )
        self.assertEqual(settings.CORS_ORIGINS, ["https://app.neuraevo.com"])

    def test_production_multiple_explicit_origins_ok(self):
        settings = _settings(
            ENVIRONMENT="production",
            CORS_ORIGINS=[
                "https://app.neuraevo.com",
                "https://admin.neuraevo.com",
            ],
        )
        self.assertEqual(len(settings.CORS_ORIGINS), 2)

    def test_production_comma_separated_string_is_parsed_and_accepted(self):
        # The pre-existing comma-string parser still runs before the safety
        # validator, so env-provided origins work in production.
        settings = _settings(
            ENVIRONMENT="production",
            CORS_ORIGINS="https://a.neuraevo.com, https://b.neuraevo.com",
        )
        self.assertEqual(
            settings.CORS_ORIGINS,
            ["https://a.neuraevo.com", "https://b.neuraevo.com"],
        )

    def test_production_comma_string_wildcard_still_fails(self):
        with self.assertRaises(ValidationError):
            _settings(ENVIRONMENT="production", CORS_ORIGINS="*")


if __name__ == "__main__":
    unittest.main()
