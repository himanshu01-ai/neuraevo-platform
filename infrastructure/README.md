# Infrastructure

Production Infrastructure as Code for NeuraEvo. Everything here is derived from
the application in this repository — no speculative services.

## What runs where

```
                    ┌──────────────┐        ┌────────────────────────┐
   Browser  ──────► │   Vercel     │  SSR   │        Render          │
                    │  (frontend)  │ ─────► │  neuraevo-api (Docker) │
                    │  Next.js 15  │  API   │  FastAPI / uvicorn     │
                    └──────────────┘        │          │             │
                           ▲                │          ▼             │
                           └── client API ──┼──► neuraevo-db          │
                                            │    (managed Postgres)   │
                                            └────────────────────────┘
```

- **Backend API + database → Render**, declared in the repo-root [`render.yaml`](../render.yaml) (Render discovers Blueprints only at the repository root).
- **Frontend → Vercel** (recommended; Next.js-native). A container image is also
  provided for self-hosting — see [`docker/frontend.Dockerfile`](docker/frontend.Dockerfile).

Deployment documentation set:

- [`../docs/deployment.md`](../docs/deployment.md) — deployment guide (architecture, services, env vars, steps, rollback).
- [`../docs/launch-checklist.md`](../docs/launch-checklist.md) — production launch (go-live) checklist.
- [`../docs/operations-runbook.md`](../docs/operations-runbook.md) — day-2 operations & incident response.

## Files

| Path | Purpose |
|---|---|
| `../render.yaml` | Render Blueprint (at the repo root): backend web service + managed PostgreSQL |
| `docker/backend.Dockerfile` | Production backend image (Python 3.12, non-root) |
| `docker/frontend.Dockerfile` | Production frontend image (Node 22, multi-stage, non-root) |
| `../backend/docker-entrypoint.sh` | Container entrypoint: DB-scheme normalise → migrate → serve |

## Why this shape (derived from the code)

- **No Nginx / Prometheus / Grafana / Redis / worker.** The backend is a single
  stateless FastAPI app with no `/metrics` endpoint, no background workers, and
  no scheduler process (the "scheduler" module is a pure, timer-free planning
  model). The hosting platform provides TLS, routing, and metrics.
- **Vanilla PostgreSQL.** No `pgvector` column or Qdrant call exists at runtime;
  the schema is owned by the 12 Alembic migrations in `backend/alembic/`.
- **No object storage.** Nothing in the backend uses Supabase Storage or S3.
- **Single instance.** The rate limiter and workflow runtime keep per-process
  in-memory state — encoded as `numInstances: 1` and a single uvicorn worker.

## Quick reference

```bash
# Backend image (build context is ./backend)
docker build -f infrastructure/docker/backend.Dockerfile ./backend

# Frontend image (build context is ./frontend)
docker build -f infrastructure/docker/frontend.Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://<api-host>/api/v1 ./frontend
```
