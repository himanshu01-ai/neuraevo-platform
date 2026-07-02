"""Application configuration.

Loads settings from environment variables (and an optional ``.env`` file)
using ``pydantic-settings``. A single cached :class:`Settings` instance is
exposed via :func:`get_settings` so the rest of the application shares one
source of truth for configuration.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # --- Logging ---------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO")

    # --- Database --------------------------------------------------------
    # PostgreSQL connection URL. Optional in Sprint 1A so the application can
    # boot without a live database (see app.core.database).
    DATABASE_URL: str | None = Field(default=None)

    # --- Authentication / JWT -------------------------------------------
    # IMPORTANT: override JWT_SECRET_KEY via the environment in any non-local
    # deployment. The default below is for local development only.
    JWT_SECRET_KEY: str = Field(default="dev-insecure-change-me")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

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


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


settings = get_settings()
