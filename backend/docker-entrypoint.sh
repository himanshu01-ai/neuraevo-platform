#!/usr/bin/env sh
# NeuraEvo backend container entrypoint — deployment glue only, no app logic.
#
# 1. Driver scheme. Managed Postgres providers (Render, Supabase, Neon, …) hand
#    out a plain `postgresql://` connection string. SQLAlchemy would route that
#    to psycopg2, which this image does not install; rewrite the scheme so it
#    selects psycopg v3 — the `psycopg[binary]` driver pinned in requirements.txt.
#    A URL that already names a driver (e.g. postgresql+psycopg://) or is not
#    Postgres (e.g. sqlite://) passes through untouched.
# 2. Migrations. Apply Alembic migrations to head. Idempotent: a no-op once the
#    database is already current. Safe because this service runs as a single
#    instance (see render.yaml / docs/deployment.md).
# 3. Serve. exec so uvicorn becomes PID 1 and receives SIGTERM directly for a
#    clean shutdown. A SINGLE worker on purpose: the auth/AI rate limiter and the
#    workflow runtime keep per-process in-memory state, so a second worker would
#    split that state. Scale up, not out.
set -eu

case "${DATABASE_URL:-}" in
  postgresql://*)
    DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgresql://}"
    export DATABASE_URL
    ;;
  postgres://*)
    DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgres://}"
    export DATABASE_URL
    ;;
esac

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
