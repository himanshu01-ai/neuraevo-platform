"""NeuraEvo backend application entrypoint.

Configures the FastAPI application: logging, CORS, lifespan (database engine
initialization/disposal), and API v1 router registration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import dispose_engine, init_engine
from app.core.dependencies import build_app_session_provider
from app.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of application resources.

    Owns the lifetime of the single application-scoped Gemini Live session
    provider (H1 hardening): it is built once at startup and stored on
    ``app.state`` (application state — not a module global), and disposed once
    at shutdown via its :meth:`shutdown`, which stops the background event loop
    and reclaims its thread so no loop or thread leaks. The provider is optional
    — the app still boots when Gemini is not configured.
    """
    logger.info("Starting %s (%s)", settings.PROJECT_NAME, settings.ENVIRONMENT)
    init_engine()
    app.state.session_provider = build_app_session_provider()
    if app.state.session_provider is not None:
        logger.info("Gemini Live session provider initialized (application-scoped).")
    yield
    provider = getattr(app.state, "session_provider", None)
    if provider is not None:
        provider.shutdown()
        app.state.session_provider = None
        logger.info("Gemini Live session provider shut down.")
    dispose_engine()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory: build and configure the FastAPI instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
