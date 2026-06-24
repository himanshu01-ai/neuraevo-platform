"""Database connection layer (PostgreSQL).

Sprint 1A scope: provide the SQLAlchemy engine/session *placeholder* and a
``get_db`` dependency. The engine is created lazily so the application can
start even when ``DATABASE_URL`` is not configured yet. No models or queries
are defined here.
"""

from collections.abc import Iterator
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Module-level singletons, initialized lazily by ``init_engine``.
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


class Base(DeclarativeBase):
    """Declarative base class for future ORM models."""


def init_engine() -> Optional[Engine]:
    """Create the SQLAlchemy engine and session factory if configured.

    Returns the engine, or ``None`` when ``DATABASE_URL`` is not set. This is a
    placeholder: it wires up the connection but performs no schema work.
    """
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    if not settings.DATABASE_URL:
        logger.warning(
            "DATABASE_URL is not set; database engine not initialized. "
            "Running without a database connection."
        )
        return None

    _engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    logger.info("Database engine initialized.")
    return _engine


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session.

    Raises ``RuntimeError`` if the engine has not been configured, so callers
    fail loudly rather than silently operating without a database.
    """
    if _SessionLocal is None:
        init_engine()
    if _SessionLocal is None:
        raise RuntimeError(
            "Database is not configured. Set DATABASE_URL to enable database access."
        )

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Dispose of the engine connection pool (called on shutdown)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        logger.info("Database engine disposed.")
    _engine = None
    _SessionLocal = None
