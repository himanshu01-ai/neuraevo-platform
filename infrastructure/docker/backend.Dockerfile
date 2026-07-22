# syntax=docker/dockerfile:1
#
# NeuraEvo backend — FastAPI served by uvicorn on Python 3.12.
#
# Build context is ./backend (see infrastructure/render/render.yaml, or build
# locally with:  docker build -f infrastructure/docker/backend.Dockerfile ./backend).
#
# Single stage on purpose: every runtime dependency in requirements.txt ships as
# a prebuilt wheel (psycopg[binary], bcrypt, …), so there is nothing to compile
# and a separate build stage would add complexity without shrinking the image.
FROM python:3.12-slim-bookworm

# Predictable, quiet, cache-free Python in a container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code, migrations, and the entrypoint (context is ./backend).
COPY . .

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Documented for local runs; on Render the platform provides $PORT.
EXPOSE 8000

# The entrypoint normalises the DB URL scheme, applies migrations, then serves.
# Invoked via `sh` so it needs no executable bit set in the build context
# (keeps the image identical whether built on Linux, macOS, or Windows).
# Liveness probe: GET /api/v1/health (see app/api/v1/health.py).
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
