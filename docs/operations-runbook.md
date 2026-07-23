# Operations runbook

Day-2 operations for NeuraEvo in production: how to deploy, roll back, migrate,
observe, and respond to incidents. Every procedure below maps to something the
repository actually provides — no tooling the project does not use.

**Documentation set** (one coherent set — start with whichever fits the task):

- [`deployment.md`](deployment.md) — **deployment guide**: the architecture, the
  services, environment variables, and how a deploy works. Read this first.
- [`launch-checklist.md`](launch-checklist.md) — **launch checklist**: the
  one-time go-live gate.
- [`environment.md`](environment.md) — **environment configuration**: variable
  ownership, secrets, and per-platform setup.
- [`dns-plan.md`](dns-plan.md) — **DNS plan**: domains, records, TLS, and email
  authentication.
- **`operations-runbook.md`** (this doc) — **run it in production**: routine ops
  and incident response.

---

## System at a glance

- **Backend** `neuraevo-api` — FastAPI/uvicorn, Docker, on Render. **Single
  instance, single worker** (`numInstances: 1`); the auth/AI rate limiter and the
  workflow runtime hold per-process state, so this is not negotiable without
  externalising that state.
- **Database** `neuraevo-db` — Render managed PostgreSQL 16. Only datastore.
- **Frontend** — Next.js 15 on Vercel (or the provided container image).
- **CI** — [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): backend
  tests, frontend checks, both Docker builds.

Full topology and rationale: [`deployment.md` → Architecture](deployment.md#architecture).

## Where to look

| You need | Go to |
|---|---|
| Backend logs, metrics, redeploy, rollback, shell, env vars | Render dashboard → `neuraevo-api` |
| Database status, connection info, backups | Render dashboard → `neuraevo-db` |
| Frontend deploys, rollback, env vars | Vercel dashboard → project |
| Build/test status | GitHub Actions → CI |
| Is the backend up? | `GET /api/v1/health` |
| What can this host run? | `GET /api/v1/health/capabilities` |

---

## Routine operations

### Deploy a change

Push to the tracked branch. Render (`autoDeploy`) rebuilds the backend image and,
on container start, [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh)
runs `alembic upgrade head` before serving. Vercel rebuilds the frontend. A
failed migration fails the deploy (the container exits before serving) — the
previous version keeps running. Steps: [`deployment.md` → Deploy workflow](deployment.md#deploy-workflow).

### Update an environment variable

Set it in the Render dashboard (`neuraevo-api` → Environment) and redeploy.
Backend settings and their meanings: [`backend/.env.example`](../backend/.env.example) /
[`config.py`](../backend/app/core/config.py).

**Frontend caveat:** `NEXT_PUBLIC_*` values are inlined at **build time**, so
changing `NEXT_PUBLIC_API_BASE_URL` (or any adapter switch) requires a **frontend
rebuild**, not just a restart.

### Rotate secrets

- **`JWT_SECRET_KEY`** — rotating it changes every token's signature, so **all
  existing access and refresh tokens become invalid and every user must log in
  again**. There is no partial rotation. (For revoking a single user without a
  global rotation, the per-user `token_epoch` / `epc` claim already invalidates
  their tokens on logout and password reset.)
- **`ANTHROPIC_API_KEY`** — set the new key and redeploy; AI features pick it up
  on restart.
- **Database credentials** — rotate from the Render database page; `DATABASE_URL`
  is re-injected via `fromDatabase` on the next deploy.

### Run or inspect migrations manually

Migrations normally run automatically on deploy. To inspect or act by hand, open
a shell on `neuraevo-api` (Render → Shell). Because a fresh shell sees the raw
`postgresql://` `DATABASE_URL` (the entrypoint only normalises it for the serving
process), select the installed psycopg v3 driver first:

```sh
export DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgresql://}"
alembic current        # current revision
alembic history        # full history (single head: a3f8b7d64c21)
alembic upgrade head   # apply pending
alembic downgrade -1   # step back one (all 12 migrations are reversible)
```

### Scale

**Vertical only.** Raise the Render instance size. Do **not** add instances or
uvicorn workers while the rate limiter and workflow runtime keep in-process
state — that is the first thing to externalise before scaling out. Pool sizing
for a larger instance: `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` (see `config.py`).

---

## Observability

- **Liveness:** `GET /api/v1/health` — constant-time, **does not touch the
  database**. A green check means the process is up, not that the DB is reachable
  (prove DB health via a login/read path — see the launch checklist §10).
- **Capabilities:** `GET /api/v1/health/capabilities` — which runtime
  capabilities are available (`Browser` reports `unavailable` unless Chromium is
  installed; that is expected).
- **Access logs:** one structured line per request from
  [`middleware.py`](../backend/app/core/middleware.py):
  `http_request method=… path=… status=… duration_ms=… request_id=…`.
- **Correlation:** every response carries `X-Request-ID` (echoed from the request
  when supplied) and `X-Response-Time-ms`. To trace a report of a failed request,
  get its `X-Request-ID` and grep the Render logs for `request_id=<id>`.
- **Metrics:** Render service metrics (CPU/memory/health). No in-app `/metrics`
  endpoint and no external APM/error tracking is wired (see Constraints).

---

## Incident playbooks

Symptom → most likely cause (grounded in this codebase) → action.

### Backend won't start / boot loop
Check the startup logs. The app **fails fast by design** when misconfigured in
production:
- `CORS_ORIGINS` contains `*` → set explicit origins.
- `JWT_SECRET_KEY` is still the dev default → set a real secret (the blueprint's
  `generateValue` normally handles this).
- `DATABASE_URL` unset/unreachable → the entrypoint's `alembic upgrade head` (or
  the app) errors before serving.
- A migration failed → see below.

### Migration failed on deploy
The container exits before serving and the deploy fails; the previous version
stays live. Read the Alembic error in the deploy logs, fix the migration or the
database state, and redeploy. If a bad migration was already applied, downgrade
(see “Run migrations manually”). Prefer forward-fixes over downgrades of
destructive migrations.

### Database connectivity errors
- Confirm `neuraevo-db` is up (Render database page).
- Driver: the serving process should have `postgresql+psycopg://` (entrypoint
  normalises it); a manual shell must export it (see above).
- After idle periods: `pool_pre_ping` + `DB_POOL_RECYCLE_SECONDS` guard against
  server-dropped connections; raise `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` if the single
  instance saturates the pool under load.

### 5xx spike
Grep logs by `request_id`. Every handled error returns the `{"detail": …}`
contract; an unexpected 500 is logged with its correlation id. Common backend
causes: database errors (above) or the Anthropic upstream (below).

### AI features failing or slow
- 401/permission from the provider → check `ANTHROPIC_API_KEY`.
- Timeouts → `ANTHROPIC_TIMEOUT_SECONDS`; model via `ANTHROPIC_MODEL`; output cap
  `ANTHROPIC_MAX_TOKENS`.
- Users hitting `429` on generation → the per-user AI rate limit
  (`AI_RATE_LIMIT_ATTEMPTS` / `_WINDOW_SECONDS`), which is **in-process and resets
  on restart**.

### 429 Too Many Requests
Auth or AI rate limiting (`AUTH_RATE_LIMIT_*` / `AI_RATE_LIMIT_*`). Tune the
window/attempts if legitimate traffic is affected. Remember these counters are
per-process and reset on redeploy.

### 413 Request Entity Too Large
Body exceeded `MAX_REQUEST_BODY_BYTES` (default 2 MB). Raise it only if a genuine
payload needs it.

### CORS errors in the browser
`CORS_ORIGINS` must list the exact frontend origin(s). Update it after any DNS /
domain change, then redeploy the backend.

### Frontend can’t reach the backend
`NEXT_PUBLIC_API_BASE_URL` is baked at build time — verify it points at the live
API and **rebuild** the frontend if it changed. Then confirm the backend’s
`CORS_ORIGINS` includes the frontend origin.

### Verification / reset emails not arriving
`EMAIL_PROVIDER` defaults to `console` (logs only). Production must set
`EMAIL_PROVIDER=smtp` and the `SMTP_*` variables.

### `health/capabilities` shows Browser `unavailable`
Expected — Chromium is not installed in the image. Enable it only if a workflow
needs Browser steps (`python -m playwright install chromium` + system libs; see
[`deployment.md`](deployment.md)).

---

## Backups & restore

Render managed-Postgres backups are the recovery mechanism (only datastore; no
object storage or external cache). Verify backups are enabled and **test a
restore** before relying on it. Schema changes are reversible (all 12 migrations
define `downgrade()`), but destructive migrations can still lose data. Full
checklist: [`launch-checklist.md` → Backups](launch-checklist.md#7-backups).

## Rollback

- **Backend:** Render **Rollback** to the previous image. Migrations are **not**
  auto-reversed — if a schema change must be undone, `alembic downgrade` it (see
  above). Prefer forward-fixes.
- **Frontend:** promote the previous Vercel deployment (immutable, instant, no DB
  coupling).
- Plan the order in advance: stop traffic → decide whether a downgrade is needed
  → roll back app → optionally downgrade. Detail:
  [`launch-checklist.md` → Rollback](launch-checklist.md#11-rollback-plan).

## Routine maintenance

- **Dependencies:** update `backend/requirements.txt` / `frontend/package.json`,
  keep CI green (it runs the full backend suite, frontend checks, and both image
  builds), then deploy.
- **Authoring migrations:** `alembic revision --autogenerate -m "…"` from
  `backend/`; keep a **single head** (merge if two heads appear) so the
  entrypoint’s `upgrade head` stays unambiguous.
- **Config drift:** any new `Settings` field must be documented in
  `backend/.env.example` — `tests/test_config_documentation.py` enforces this.

## Operational constraints (know these before you page someone)

- **Single instance / single worker** — no horizontal scaling until in-process
  state is externalised.
- **In-process rate limits reset** on every restart/redeploy.
- **Capability workspaces are ephemeral** — Filesystem/Email/Calendar/GitHub
  steps write under the system temp dir; data is lost on restart and not shared.
  Nothing durable lives outside PostgreSQL.
- **No external error tracking / APM** — monitoring is Render metrics + structured
  logs + the health endpoints.
- **No object storage, no vector search at runtime** — nothing to operate there.
