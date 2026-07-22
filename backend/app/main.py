"""NeuraEvo backend application entrypoint.

Configures the FastAPI application: logging, OpenAPI metadata, request-context
middleware (correlation id + timing), the global exception handlers that give
every failure one JSON contract, CORS, lifespan (database engine
initialization/disposal), and API v1 router registration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import dispose_engine, init_engine
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.schemas.error import ErrorResponse
from app.services.runtime.capability_dependencies import log_startup_report
from app.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

#: A one-line description per OpenAPI tag, so the Swagger sidebar reads as a map
#: of the platform rather than a bare list. Order is roughly the user journey:
#: sign in, build an employee, talk to it, delegate work, collaborate.
_OPENAPI_TAGS = [
    {"name": "Health", "description": "Liveness and runtime-capability readiness for operators."},
    {"name": "Auth", "description": "Registration, login, token refresh, email verification, and password reset."},
    {"name": "Employees", "description": "AI employee lifecycle: create, configure, capabilities, assignments, and activity."},
    {"name": "Blueprints", "description": "The employee's blueprint — its persisted definition."},
    {"name": "Blueprint Generation", "description": "AI-assisted drafting of a blueprint from interview data."},
    {"name": "Blueprint Versions", "description": "Immutable blueprint version history and restore."},
    {"name": "Interview Questions", "description": "Authoring the interview that shapes an employee."},
    {"name": "Interview Answers", "description": "Answers captured during the interview."},
    {"name": "Interview Sessions", "description": "Interview session lifecycle."},
    {"name": "Interview Session Questions", "description": "Per-session question execution."},
    {"name": "Conversations", "description": "Employee-scoped conversation records."},
    {"name": "Conversation Hub", "description": "User-scoped conversations and the channel-aware turn (text and voice)."},
    {"name": "Conversation Generation", "description": "Generating an assistant reply for a conversation."},
    {"name": "Conversation Context", "description": "The assembled context behind a conversation reply."},
    {"name": "Conversation Runtime", "description": "The runtime AI execution pipeline for a conversation."},
    {"name": "Messages", "description": "Conversation messages (the transcript)."},
    {"name": "AI Context", "description": "AI context inspection."},
    {"name": "Memories", "description": "The Memory Engine — an employee's stored memories."},
    {"name": "Memory Integration", "description": "Cross-domain memory: user-wide memories and task/workflow references."},
    {"name": "Memory Context", "description": "Memory selected for runtime context assembly."},
    {"name": "Tasks", "description": "The Task Engine — described work, launched on the workflow runtime."},
    {"name": "Workflows", "description": "Authored workflows."},
    {"name": "Workflow Executions", "description": "Recorded workflow runs and their history."},
    {"name": "Collaboration", "description": "Participants, shares, the activity timeline, and the notification inbox."},
]

_DESCRIPTION = (
    "The NeuraEvo platform API — a voice-first personal AI employee platform.\n\n"
    "**Errors.** Every error response is JSON of the shape `{\"detail\": ...}`: a "
    "human-readable string for handled errors, and a list of field-level objects "
    "for request-validation (422) errors. Every response carries an "
    "`X-Request-ID` correlation header (echoed from the request when supplied).\n\n"
    "**Auth.** Protected endpoints require a Bearer *access* token from `/auth`."
)


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
        version=settings.API_VERSION,
        summary="Voice-first personal AI employee platform API.",
        description=_DESCRIPTION,
        openapi_tags=_OPENAPI_TAGS,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Every failure returns the one `{"detail": ...}` JSON contract (Sprint 24).
    register_exception_handlers(app)

    # Middleware stack. add_middleware makes the *last* added the outermost, so
    # these are declared innermost-first. The intent, outermost → innermost:
    #   RequestContext  — assigns the correlation id first and stamps id + timing
    #                     onto every response (including 413s and errors).
    #   SecurityHeaders — hardening headers on every response.
    #   CORS            — cross-origin headers.
    #   BodySizeLimit   — refuses an oversized body early, but after the id exists.
    #
    # Credentials are enabled only with explicit origins: a wildcard origin with
    # credentials would let any site make credentialed requests, so with the
    # permissive development default (``*``) credentials are off. Production must
    # list explicit origins (enforced at settings load), where credentials are safe.
    allow_all_origins = "*" in settings.CORS_ORIGINS
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=not allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-ms"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # Document the one universally-true error response — an unexpected 500 can
    # come from any endpoint — against the shared ErrorResponse schema, so the
    # OpenAPI document advertises the contract the safety-net handler guarantees.
    # Additive: it annotates the docs only and changes no runtime behaviour.
    app.include_router(
        api_router,
        prefix=settings.API_V1_PREFIX,
        responses={
            500: {
                "model": ErrorResponse,
                "description": "Unexpected server error (returned as JSON).",
            }
        },
    )

    return app


app = create_app()
