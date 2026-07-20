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
from app.services.runtime.capability_dependencies import log_startup_report
from app.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of application resources."""
    logger.info("Starting %s (%s)", settings.PROJECT_NAME, settings.ENVIRONMENT)
    init_engine()
    # Sprint 18.9: say at startup which runtime capabilities this host can
    # actually run, so a missing browser is found in the boot log rather than in
    # a failed workflow. Deliberately non-fatal — an optional capability that
    # was never installed should degrade one feature, not refuse to serve.
    log_startup_report()
    yield
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
