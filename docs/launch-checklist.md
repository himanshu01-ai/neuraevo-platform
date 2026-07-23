# Production launch checklist

A go-live checklist for NeuraEvo, derived entirely from this repository and the
deployment defined in [`infrastructure/`](../infrastructure/) and
[`deployment.md`](deployment.md). Every item maps to something the project
actually has; nothing here assumes tooling the codebase does not use.

Architecture recap (see [`deployment.md`](deployment.md)): **backend API +
managed PostgreSQL on Render**, **frontend (Next.js) on Vercel**, no other
services. The backend runs as a **single instance / single uvicorn worker** by
design (in-process rate limiter and workflow runtime state).

Legend: `[ ]` to do · items marked **(blocker)** should pass before taking real traffic.

**Documentation set:** the [deployment guide](deployment.md) explains the
architecture and how a deploy works; the [environment configuration](environment.md)
reference covers every variable and who owns it; the [DNS plan](dns-plan.md)
covers domains, TLS, and email DNS; this checklist is the one-time go-live gate;
the [operations runbook](operations-runbook.md) covers day-2 operations and
incident response once you are live.

---

## 1. Infrastructure

- [ ] Render Blueprint launched from the repo-root [`render.yaml`](../render.yaml); it created `neuraevo-api` (web) and `neuraevo-db` (Postgres 18).
- [ ] Confirm the pinned plan slugs (`starter` web, `basic-256mb` db) are still valid Render plans, and sized for expected load.
- [ ] `neuraevo-api` is on an **always-on** plan (not free) — no cold starts for an API.
- [ ] **(blocker)** `numInstances: 1` is preserved and no extra uvicorn workers are added — the auth/AI rate limiter and workflow runtime keep per-process state; scaling out or adding workers splits it.
- [ ] Backend and database are in the **same Render region** (`oregon` in the blueprint).
- [ ] Database `ipAllowList: []` is preserved (no public DB ingress; reachable only from Render services).
- [ ] Base images build as pinned: backend `python:3.12-slim-bookworm`, frontend `node:22-bookworm-slim` (Node ≥22 per `frontend/package.json` engines).

## 2. Deployment

- [ ] **(blocker)** `.github/workflows/ci.yml` is green on the release commit (backend tests on Python 3.12, frontend typecheck/lint/test/build on Node 22, both Docker images build).
- [ ] Backend image builds from [`infrastructure/docker/backend.Dockerfile`](../infrastructure/docker/backend.Dockerfile) with context `./backend`.
- [ ] On deploy, [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh) runs in order: normalize DB URL scheme → `alembic upgrade head` → `exec uvicorn` on `$PORT`.
- [ ] **(blocker)** Migrations apply cleanly: single head is `a3f8b7d64c21` (`alembic heads`), so `upgrade head` is unambiguous.
- [ ] Frontend deployed to Vercel with project root `frontend/` (or self-hosted via [`infrastructure/docker/frontend.Dockerfile`](../infrastructure/docker/frontend.Dockerfile)).
- [ ] **(blocker)** `NEXT_PUBLIC_API_BASE_URL` is set to the backend URL **before** the frontend build (it is inlined at build time; changing it later requires a rebuild).
- [ ] `autoDeploy` behavior on the tracked branch is understood (a push rebuilds the backend and applies new migrations automatically).

## 3. Environment variables

Backend settings live in [`backend/app/core/config.py`](../backend/app/core/config.py) and are all documented in [`backend/.env.example`](../backend/.env.example) (kept in sync by `tests/test_config_documentation.py`). Frontend public vars are in [`frontend/lib/env.ts`](../frontend/lib/env.ts) / [`frontend/.env.example`](../frontend/.env.example).

Set in the Render dashboard before first deploy:

- [ ] **(blocker)** `ENVIRONMENT=production` (enables the production security gates).
- [ ] **(blocker)** `CORS_ORIGINS` = explicit frontend origin(s), comma-separated — **the app refuses to boot in production if this contains `*`**.
- [ ] **(blocker)** `ANTHROPIC_API_KEY` set (required for blueprint/conversation generation).
- [ ] `FRONTEND_BASE_URL` = public frontend URL (used to build links in verification/reset emails).
- [ ] `JWT_SECRET_KEY` present via `generateValue: true` — confirm it is **not** the dev default (the app refuses to boot in production if it is).
- [ ] `DATABASE_URL` wired via `fromDatabase` (auto); the entrypoint rewrites `postgresql://` → `postgresql+psycopg://`.
- [ ] **Email delivery:** if account email (verification / password reset) must actually send, set `EMAIL_PROVIDER=smtp` and the `SMTP_*` vars. The default `console` provider only logs emails — users would never receive them.
- [ ] Review remaining tunables if you need non-defaults: token TTLs, rate-limit windows (`AUTH_/AI_RATE_LIMIT_*`), `MAX_REQUEST_BODY_BYTES`, `DB_POOL_*`.
- [ ] Frontend: `NEXT_PUBLIC_API_BASE_URL` set; the 7 `NEXT_PUBLIC_*_ADAPTER` switches left at `backend` (mock is for offline UI work only).
- [ ] No secrets committed — `render.yaml` references names only; `.env` is gitignored.

## 4. Security

Backend hardening is implemented (Sprint 24–25); confirm it is active in production:

- [ ] `SECURITY_HEADERS_ENABLED=true` (default) — every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and a restrictive `Content-Security-Policy` (`default-src 'none'`). Source: [`security_headers.py`](../backend/app/core/security_headers.py).
- [ ] **HSTS** present on HTTPS responses in production (emitted only when `is_production` **and** the client used HTTPS; honors `X-Forwarded-Proto` behind the platform proxy).
- [ ] **(blocker)** CORS is not wildcard in production and credentials handling is correct (credentials are enabled only with explicit origins).
- [ ] Oversized requests are rejected with `413` (`MAX_REQUEST_BODY_BYTES`, default 2 MB) — see [`middleware.py`](../backend/app/core/middleware.py).
- [ ] Per-user AI-endpoint rate limiting is enabled (`AI_RATE_LIMIT_ENABLED`) and auth rate limiting is on (`AUTH_RATE_LIMIT_ENABLED`). Note: these limiters are **in-process** and reset on restart/redeploy (single-instance is what makes them coherent).
- [ ] Passwords are bcrypt-hashed; email-verification and password-reset tokens are stored as SHA-256 hashes and are single-use (Sprint 18.1A) — no plaintext secrets at rest beyond the DB credentials.
- [ ] Container runs as non-root (uid 10001 in both Dockerfiles); `.dockerignore` keeps `.env`, `.venv`, `.git`, tests out of images.
- [ ] The `/api/v1/health/capabilities` output reveals no host paths/versions/secrets (by design) and is safe to expose.

## 5. HTTPS / TLS

- [ ] Backend served over HTTPS (Render-managed TLS); verify the certificate is issued and valid.
- [ ] Frontend served over HTTPS (Vercel-managed TLS).
- [ ] `X-Forwarded-Proto` reaches the app as `https` (platform default) so HSTS is emitted — verify with a response header check.
- [ ] No mixed content: `NEXT_PUBLIC_API_BASE_URL` uses `https://`.

## 6. DNS

- [ ] Custom domains added to the Render web service and the Vercel project, with the required DNS records created and propagated.
- [ ] After DNS is final, update and re-verify the three URL-bound settings: **backend** `CORS_ORIGINS` and `FRONTEND_BASE_URL`, and **frontend** `NEXT_PUBLIC_API_BASE_URL` (the last one requires a frontend rebuild).
- [ ] TTLs are sane for launch (lower during cutover, raise afterward).

## 7. Backups

- [ ] Render managed-Postgres automated backups are enabled and the retention window is confirmed (this is the only datastore — no object storage, no external cache to back up).
- [ ] A **restore has been tested** at least once (provision from a backup / point-in-time and confirm the app boots against it) — a backup is only real once restored.
- [ ] Migration reversibility is understood: all 12 migrations define `downgrade()`, so a schema change *can* be reversed with `alembic downgrade`, but destructive migrations may still lose data — prefer forward-fixes.

## 8. Monitoring & logging

- [ ] Render service metrics (CPU / memory / instance health) reviewed; alerts configured on the always-on instance.
- [ ] Log stream confirmed: the app emits one structured access line per request with method, path, status, duration, and a correlation id. Every response carries `X-Request-ID` (echoed from the request when supplied) and `X-Response-Time-ms` (see [`middleware.py`](../backend/app/core/middleware.py)).
- [ ] Liveness monitored at `GET /api/v1/health` (constant-time). **Note:** this endpoint does **not** touch the database — a green health check proves the process is up, not that the DB is reachable (see §10).
- [ ] `GET /api/v1/health/capabilities` reviewed once to confirm which runtime capabilities are available (Browser will report `unavailable` unless Chromium is installed — that is expected, not an error).
- [ ] **Gap acknowledged:** no external error tracking / APM (Sentry, Datadog, OpenTelemetry, Prometheus) is wired in this codebase. Monitoring is platform metrics + structured logs + the health endpoints. Decide whether that is sufficient for launch.

## 9. Validation (pre-cutover)

- [ ] Backend test suite green on the release commit: `cd backend && PYTHONPATH=. python -m unittest discover -s tests -p "test_*.py"` (includes the performance and config-doc guards).
- [ ] Frontend green: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`.
- [ ] Both Docker images build (via CI `docker-build` job).
- [ ] `render.yaml` internally consistent (health path, single instance, env references resolve, DB reference matches).
- [ ] OpenAPI document generates and looks correct at `/docs` (Swagger) / `/api/v1/openapi.json`.
- [ ] Config fail-fast verified in a staging-like env: booting with `ENVIRONMENT=production` and a wildcard `CORS_ORIGINS` (or the dev JWT secret) is **rejected** at startup.

## 10. Post-deployment verification (smoke test on the live URLs)

- [ ] `GET /api/v1/health` → `200` with `{"status":"ok","environment":"production"}`.
- [ ] **(blocker) Database connectivity proven** through a DB-touching path (health alone does not): register a user or log in, then read a protected resource (e.g. list employees). This exercises migrations-applied schema + DB + auth end to end.
- [ ] Response headers on a live request include `X-Request-ID`, `X-Response-Time-ms`, the security headers, and (over HTTPS) `Strict-Transport-Security`.
- [ ] CORS: a request from the real frontend origin succeeds; a request from an unlisted origin is refused.
- [ ] A `429` is returned when auth/AI rate limits are exceeded (spot check).
- [ ] An oversized body returns `413`.
- [ ] Frontend loads over HTTPS, reaches the backend (`NEXT_PUBLIC_API_BASE_URL` correct), and a full flow works: sign up / log in → create an AI employee → send a conversation turn (confirms `ANTHROPIC_API_KEY`).
- [ ] If email is required: trigger a verification/reset and confirm delivery (validates `EMAIL_PROVIDER=smtp` + `SMTP_*`; `console` will not send).
- [ ] Error contract intact: a 404 / 422 returns the `{"detail": ...}` shape with a correlation id.

## 11. Rollback plan

- [ ] **Backend:** use Render **Rollback** to redeploy the previous image. Understand that Alembic migrations are **not** auto-reversed — if the bad deploy included a schema change that must be undone, run `alembic downgrade <rev>` against the DB (all migrations are reversible; destructive ones need care). Prefer forward-fixes.
- [ ] **Frontend:** promote the previous Vercel deployment (immutable; instant; no DB coupling).
- [ ] **Ordering:** because backend + DB share state, decide the rollback order in advance (usually: stop traffic → assess whether a schema downgrade is needed → roll back app → optionally downgrade).
- [ ] A recent database backup exists immediately before cutover (see §7) as the last-resort recovery point.

---

## Not covered by the current project (know before launch)

These are **intentional scope facts**, not TODOs invented here — call them out so nobody assumes otherwise:

- **No horizontal scaling.** Single instance / single worker only, until the in-process rate limiter and workflow runtime state are externalized.
- **In-process rate limits reset** on every restart/redeploy.
- **No object storage.** Capability workspaces (Filesystem/Email/Calendar/GitHub steps) write under the system temp dir and are **ephemeral** — lost on restart and not shared across instances. Nothing durable is stored outside PostgreSQL.
- **No external error tracking / APM** (see §8).
- **Browser capability is off by default** (Chromium not installed in the image); enabling it needs `python -m playwright install chromium` plus its system libraries and a heavier image (see [`deployment.md`](deployment.md)).
- **Vector search is not active** (no `pgvector` column or Qdrant call at runtime); no vector infrastructure to provision.
