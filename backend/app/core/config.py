"""Application configuration.

Loads settings from environment variables (and an optional ``.env`` file)
using ``pydantic-settings``. A single cached :class:`Settings` instance is
exposed via :func:`get_settings` so the rest of the application shares one
source of truth for configuration.
"""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Insecure JWT secret intended for local development only. Sharing it as a
# module constant lets both the field default and the production-safety
# validator refer to the same value.
_DEV_JWT_SECRET = "dev-insecure-change-me"


class Settings(BaseSettings):
    """Strongly-typed application settings sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    PROJECT_NAME: str = "NeuraEvo"
    # Semantic version of the public API, surfaced in the OpenAPI document.
    API_VERSION: str = Field(default="1.0.0")
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # --- Logging ---------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO")

    # --- Database --------------------------------------------------------
    # PostgreSQL connection URL. Optional in Sprint 1A so the application can
    # boot without a live database (see app.core.database).
    DATABASE_URL: str | None = Field(default=None)

    # Connection-pool sizing for the production engine. Defaults match
    # SQLAlchemy's own (5 + 10) so behaviour is unchanged unless tuned, but they
    # are now knobs an operator can raise for production-scale concurrency.
    # ``POOL_RECYCLE`` refreshes a connection older than this many seconds, which
    # (with ``pool_pre_ping``) keeps a cloud Postgres from handing back a
    # server-dropped idle connection; ``-1`` disables recycling. These apply to
    # PostgreSQL only — SQLite (used in tests) uses its own pooling and ignores
    # them (see app.core.database).
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800)  # 30 minutes

    # --- Authentication / JWT -------------------------------------------
    # IMPORTANT: override JWT_SECRET_KEY via the environment in any non-local
    # deployment. The default below is for local development only, and the
    # application refuses to start with it outside ``development`` (see the
    # ``_require_secure_jwt_secret_outside_development`` validator).
    JWT_SECRET_KEY: str = Field(default=_DEV_JWT_SECRET)
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    # Clock-skew tolerance for JWT ``exp``/``iat`` validation (Sprint 25), so a
    # small difference between the signing and validating clocks does not
    # spuriously reject a just-issued token. Applied by ``decode_token``.
    JWT_LEEWAY_SECONDS: int = Field(default=30)

    # --- Security headers / transport (Sprint 25) -----------------------
    # Additive response hardening. All are configurable so a deployment can tune
    # the policy without a code change. The CSP default is restrictive because
    # this is a JSON API that serves no HTML of its own.
    SECURITY_HEADERS_ENABLED: bool = Field(default=True)
    SECURITY_CSP: str = Field(
        default="default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    SECURITY_REFERRER_POLICY: str = Field(default="no-referrer")
    SECURITY_PERMISSIONS_POLICY: str = Field(
        default="geolocation=(), microphone=(), camera=(), usb=(), payment=()"
    )
    # HSTS is emitted only in production and only over HTTPS (see the security
    # headers middleware), so it can never pin an http development host.
    HSTS_MAX_AGE_SECONDS: int = Field(default=63072000)  # two years
    HSTS_INCLUDE_SUBDOMAINS: bool = Field(default=True)

    # --- Request limits (Sprint 25) -------------------------------------
    # Reject request bodies larger than this with 413, so a single oversized
    # payload cannot exhaust memory. Generous for a JSON API.
    MAX_REQUEST_BODY_BYTES: int = Field(default=2 * 1024 * 1024)  # 2 MB

    # --- AI endpoint rate limiting (Sprint 25) --------------------------
    # A per-user cap on the expensive AI/generation endpoints, reusing the auth
    # rate limiter's abstraction. Defaults are deliberately generous so a normal
    # user is never affected; the point is to bound cost/abuse.
    AI_RATE_LIMIT_ENABLED: bool = Field(default=True)
    AI_RATE_LIMIT_ATTEMPTS: int = Field(default=60)
    AI_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60)

    # --- Email verification / password reset (Sprint 18.1A) --------------
    # Verification uses a short numeric code (entered in the UI); password
    # reset uses a long URL-safe token delivered as a link. Both are stored
    # only as SHA-256 hashes and are single-use.
    EMAIL_VERIFICATION_CODE_TTL_MINUTES: int = Field(default=15)
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = Field(default=60)

    # --- Rate limiting (Sprint 18.1A) ------------------------------------
    # Fixed-window limits for the sensitive auth endpoints. The default
    # limiter is in-process; see app/services/rate_limiter.py for the
    # multi-worker caveat.
    AUTH_RATE_LIMIT_ENABLED: bool = Field(default=True)
    LOGIN_RATE_LIMIT_ATTEMPTS: int = Field(default=10)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=300)
    EMAIL_SEND_RATE_LIMIT_ATTEMPTS: int = Field(default=5)
    EMAIL_SEND_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600)
    VERIFY_RATE_LIMIT_ATTEMPTS: int = Field(default=10)
    VERIFY_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=900)

    # --- Email delivery (Sprint 18.1A) -----------------------------------
    # ``console`` logs rendered emails (development default, no SMTP needed);
    # ``smtp`` delivers via the configured server. Authentication never talks
    # to SMTP directly — it depends on the EmailService abstraction.
    EMAIL_PROVIDER: str = Field(default="console")
    EMAIL_FROM_ADDRESS: str = Field(default="no-reply@neuraevo.com")
    EMAIL_FROM_NAME: str = Field(default="NeuraEvo")
    # Public base URL of the frontend, used to build links in emails.
    FRONTEND_BASE_URL: str = Field(default="http://localhost:3000")
    SMTP_HOST: str | None = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: str | None = Field(default=None)
    SMTP_PASSWORD: str | None = Field(default=None)
    SMTP_USE_TLS: bool = Field(default=True)
    SMTP_TIMEOUT_SECONDS: float = Field(default=10.0)

    # --- AI / Anthropic (Claude) ----------------------------------------
    # Never hardcode credentials. ANTHROPIC_API_KEY is read from the
    # environment; the model name is configurable so it is not embedded in
    # business logic.
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    ANTHROPIC_MODEL: str = Field(default="claude-sonnet-4-6")
    ANTHROPIC_TIMEOUT_SECONDS: float = Field(default=30.0)
    ANTHROPIC_MAX_TOKENS: int = Field(default=4096)

    # --- Memory ----------------------------------------------------------
    # Maximum number of memories selected for context assembly (newest first).
    MEMORY_CONTEXT_LIMIT: int = Field(default=10)

    # --- Vector Store / Qdrant ------------------------------------------
    # Connection settings for the Qdrant vector store. All optional so the app
    # boots without a configured/live Qdrant instance — Sprint 10.2 wires the
    # infrastructure only; nothing calls Qdrant yet.
    QDRANT_URL: str | None = Field(default=None)
    QDRANT_API_KEY: str | None = Field(default=None)
    QDRANT_TIMEOUT_SECONDS: float = Field(default=30.0)

    # --- CORS ------------------------------------------------------------
    # Comma-separated list of allowed origins, e.g.
    # "http://localhost:3000,https://app.neuraevo.com"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow ``CORS_ORIGINS`` to be provided as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        """True in any non-``development`` environment.

        The single place the environment gate is defined, so security features
        that must only apply to a real deployment (HSTS, the CORS wildcard
        refusal) all read the same predicate.
        """
        return self.ENVIRONMENT.strip().lower() != "development"

    @model_validator(mode="after")
    def _require_explicit_cors_origins_in_production(self) -> "Settings":
        """Fail fast when a wildcard CORS origin is used outside development.

        A wildcard origin (``*``) combined with the API's credentialed requests
        would let any site talk to a production deployment. Development keeps the
        permissive default for convenience; any other environment must list its
        real origins explicitly, and the application refuses to start otherwise —
        an invalid production CORS configuration is caught at boot, not at the
        first cross-origin request.
        """
        if (
            self.ENVIRONMENT.strip().lower() != "development"
            and "*" in self.CORS_ORIGINS
        ):
            raise ValueError(
                "CORS_ORIGINS must list explicit origins in non-development "
                f"environments (ENVIRONMENT={self.ENVIRONMENT!r}); the wildcard "
                "'*' is not permitted outside development."
            )
        return self

    @model_validator(mode="after")
    def _require_secure_jwt_secret_outside_development(self) -> "Settings":
        """Fail fast when the insecure dev JWT secret is used outside dev.

        In any non-``development`` environment the application refuses to start
        while ``JWT_SECRET_KEY`` is still the built-in development default,
        preventing forgeable tokens from a forgotten override. Development
        behaviour is unchanged (the default is allowed there).
        """
        if (
            self.ENVIRONMENT.strip().lower() != "development"
            and self.JWT_SECRET_KEY == _DEV_JWT_SECRET
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be overridden via the environment in "
                f"non-development environments (ENVIRONMENT={self.ENVIRONMENT!r}); "
                "the insecure development default is not permitted outside "
                "development."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


settings = get_settings()
