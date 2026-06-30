"""Alembic migration environment.

Wires Alembic into the application's own configuration so migrations share a
single source of truth with the running app:

* the SQLAlchemy ``Base`` / metadata from ``app.core.database``;
* every ORM model, registered by importing ``app.models`` (so
  ``--autogenerate`` can see the full schema);
* the ``DATABASE_URL`` from ``app.core.config.settings`` (loaded from ``.env``)
  — credentials are never stored in ``alembic.ini``, and the same connection
  string is used in local development and on Render.

No application configuration is duplicated here and no ORM model is modified.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

from app.core.config import settings
from app.core.database import Base

# Importing the models package registers every model on ``Base.metadata`` as a
# side effect, which is what autogenerate diffs against. Imported for its side
# effect only.
import app.models  # noqa: F401

# Alembic Config object, providing access to values in alembic.ini.
config = context.config

# Configure Python logging from alembic.ini, if a config file is present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata that ``--autogenerate`` compares against the live database.
target_metadata = Base.metadata


def _get_database_url() -> str:
    """Return the application's configured database URL, or fail loudly.

    The URL is read from ``app.core.config.settings`` (which loads ``.env``),
    keeping it the single source of truth and avoiding hardcoded credentials.
    """
    url = settings.DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in the environment or .env "
            "before running Alembic."
        )
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL; no DBAPI connection).

    The URL is passed directly (not via alembic.ini), so values containing
    percent signs — e.g. a percent-encoded ``%40`` in the password — are not
    misinterpreted by ConfigParser interpolation.
    """
    context.configure(
        url=_get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database connection."""
    # A dedicated, short-lived engine built from the application's URL.
    # ``NullPool`` is used because a migration run opens one connection and
    # exits; it must not maintain or borrow from the app's runtime pool.
    connectable = create_engine(
        _get_database_url(),
        poolclass=pool.NullPool,
        future=True,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
