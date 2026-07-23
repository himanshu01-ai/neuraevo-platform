# Environment configuration

How NeuraEvo is configured across environments: which variables exist, who owns
them, what is a secret, and how to set them safely for local development and
production. This is the canonical configuration reference; it links out to the
deployment docs rather than repeating them.

**Documentation set:**
[deployment guide](deployment.md) · [DNS plan](dns-plan.md) ·
[Cloudflare plan](cloudflare-plan.md) · [CORS & origin plan](cors-origin-plan.md) ·
[launch checklist](launch-checklist.md) ·
[operations runbook](operations-runbook.md) · **environment configuration** (this doc).

Sources of truth this document is derived from:
- Backend settings — [`backend/app/core/config.py`](../backend/app/core/config.py) (`Settings`, pydantic-settings), documented in [`backend/.env.example`](../backend/.env.example).
- Frontend settings — [`frontend/lib/env.ts`](../frontend/lib/env.ts) (Zod), documented in [`frontend/.env.example`](../frontend/.env.example).
- Production wiring — [`render.yaml`](../render.yaml).

---

## 1. Purpose

Give one place that answers, for every environment variable NeuraEvo reads:
*what it does, whether it is required, whether it is a secret, which platform
owns it, where its value comes from, and when to set it.* It exists so an
operator can configure production correctly and a developer can bootstrap
locally, without reading the source.

## 2. Environment architecture

**Canonical production domains** (approved Sprint 1.2):

| Element | URL |
|---|---|
| Frontend (Vercel) | `https://neuraevo.dev` |
| Backend API (Render) | `https://api.neuraevo.dev` |
| API base URL | `https://api.neuraevo.dev/api/v1` |
| Email sender | `no-reply@neuraevo.dev` |

Configuration is owned by the platform closest to where the value is used. NeuraEvo
is a split deployment (see [deployment.md → Architecture](deployment.md#architecture)):

```
Operator / DNS (custom domains)
        │  supplies the URL values
        ▼
Vercel (frontend)                      Render (backend service)
  owns: NEXT_PUBLIC_* (build-time)  ──► owns: app Settings env
        │                                     │        │        │
        │ client + SSR call the API           ▼        ▼        ▼
        └───────────────────────────►  PostgreSQL  Anthropic  SMTP
                                        (Render)    (API key)  (provider)
```

Ownership:

| Layer | Owns | How |
|---|---|---|
| **Vercel (frontend)** | the 9 `NEXT_PUBLIC_*` variables | Project env vars, inlined into the client bundle **at build time**. |
| **Render (backend)** | the backend `Settings` env | Service env vars; some auto-provided (see §5), some operator-set (see §4). |
| **PostgreSQL (Render managed)** | the connection string | Provisioned by the Blueprint; injected as `DATABASE_URL` via `fromDatabase`. |
| **Anthropic** | the API credential | `ANTHROPIC_API_KEY` created in the Anthropic Console, stored in Render. |
| **SMTP provider** | mail-sending credentials | `SMTP_*` created in the provider, stored in Render (only if email is enabled). |
| **DNS (e.g. Cloudflare)** | domains/TLS | No app env vars; the resulting origins feed `CORS_ORIGINS`, `FRONTEND_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL`. |

## 3. Environment files

| File | Committed? | Purpose |
|---|---|---|
| [`backend/.env.example`](../backend/.env.example) | **Yes** | Template documenting every backend `Settings` field (54) with safe placeholders/defaults. |
| [`frontend/.env.example`](../frontend/.env.example) | **Yes** | Template documenting the 9 `NEXT_PUBLIC_*` variables. |
| `backend/.env` | **No — local only** | A developer's real backend config. **Gitignored** (`.env`). |
| `frontend/.env.local` | **No — local only** | A developer's real frontend config. **Gitignored** (`.env.local`). |

Only the two `*.env.example` files are committed; they contain **placeholders,
never real values**. The `.env` / `.env.local` files are gitignored and hold real
values (including secrets) — see §7. Completeness of `backend/.env.example` is
enforced automatically by `backend/tests/test_config_documentation.py`.

## 4. Production-managed variables

Variables an operator must intentionally set for production (from the approved
Step 2 matrix). Everything else is a platform default (§5) or an internal default
that does not normally need overriding.

| Variable | Required | Secret | Platform | Source | Notes |
|---|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (AI non-functional without it) | Yes | Render | Anthropic Console | `sync:false` in `render.yaml`. |
| `CORS_ORIGINS` | Yes (prod **refuses to boot** with `*`) | No | Render | Domain / manual | Comma-separated exact frontend origin(s), e.g. `https://neuraevo.dev`. |
| `FRONTEND_BASE_URL` | Yes (email links) | No | Render | Domain / manual | Public frontend URL (`https://neuraevo.dev`) used in verification/reset mail. |
| `NEXT_PUBLIC_API_BASE_URL` | Yes (frontend → backend) | No (public) | Vercel | Backend origin | **Build-time inlined**; a change requires a frontend rebuild. Value = backend origin + `/api/v1`, i.e. `https://api.neuraevo.dev/api/v1`. |
| `EMAIL_PROVIDER` | Conditional (email delivery) | No | Render | Manual | Default `console` sends nothing; set `smtp` to deliver. |
| `SMTP_HOST` | Conditional (`smtp`) | No | SMTP provider | SMTP provider | — |
| `SMTP_USERNAME` | Conditional (`smtp`) | Yes | SMTP provider | SMTP provider | Credential. |
| `SMTP_PASSWORD` | Conditional (`smtp`) | Yes | SMTP provider | SMTP provider | Credential. |
| `EMAIL_FROM_ADDRESS` | Recommended (if email) | No | Render | Manual | Override the `no-reply@neuraevo.dev` default for your domain. |

Optional tuning only if the provider deviates from defaults: `SMTP_PORT` (587),
`EMAIL_FROM_NAME` (`NeuraEvo`). The 8 `NEXT_PUBLIC_*_ADAPTER` switches stay at
`backend` in production and need no override.

## 5. Platform-managed variables

These are provided automatically and are **not** set by hand in normal operation:

| Variable | Provided by | How | Why not manual |
|---|---|---|---|
| `DATABASE_URL` | Render | `fromDatabase` in `render.yaml`, from the managed `neuraevo-db` | Render owns the credentials/host; the value only exists once the DB is provisioned. Arrives as `postgresql://` and is rewritten to `postgresql+psycopg://` by [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh). |
| `JWT_SECRET_KEY` | Render | `generateValue: true` | Render generates and stores a strong secret once; a hand-set value risks weak/committed secrets. (Recreating the service mints a new one → all tokens invalidated.) |
| `ENVIRONMENT` | `render.yaml` | `value: production` | Fixed by the Blueprint to enable the production security gates. |
| `PORT` | Render | Injected at runtime | The platform chooses the port; the entrypoint binds `uvicorn` to `$PORT` (Dockerfile default 8000 for local runs). |

Other build/runtime variables (`NODE_ENV`, `HOSTNAME`, `NEXT_TELEMETRY_DISABLED`,
`PYTHONPATH`, `PYTHON*`/`PIP*` flags) are set by the Dockerfiles/CI and never need
operator attention.

## 6. Deployment order

Because the frontend needs the backend origin and the backend needs the frontend
origin, order matters (full steps: [deployment.md → Deploy workflow](deployment.md#deploy-workflow)):

1. **Prepare secrets** that don't depend on deployment: create the `ANTHROPIC_API_KEY` (and SMTP credentials, if email is in scope).
2. **Launch the Render Blueprint** → provisions `neuraevo-db` and `neuraevo-api`; `DATABASE_URL` and `JWT_SECRET_KEY` are auto-created.
3. **Set the backend `sync:false` vars** in Render: `ANTHROPIC_API_KEY`, and `CORS_ORIGINS` + `FRONTEND_BASE_URL` (use the final frontend domain if known). The backend migrates and starts.
4. **Deploy the frontend to Vercel** with `NEXT_PUBLIC_API_BASE_URL` = the backend origin `+ /api/v1` (must be set **before** the build).
5. **Reconcile origins:** set the backend `CORS_ORIGINS` (and `FRONTEND_BASE_URL`) to the final frontend origin, then redeploy the backend.
6. **Verify** using the [launch checklist](launch-checklist.md).

Pre-deciding custom domains removes the ordering constraint — all URL values can
then be set up front.

## 7. Security guidelines

- **Secret management.** Real secrets live only in the platform's secret store
  (Render/Vercel dashboards) or a local gitignored `.env` / `.env.local`. The
  secrets are: `DATABASE_URL`, `JWT_SECRET_KEY`, `ANTHROPIC_API_KEY`,
  `SMTP_USERNAME`, `SMTP_PASSWORD`, `QDRANT_API_KEY`. `render.yaml` declares only
  variable **names** (`sync:false` / `generateValue` / `fromDatabase`) — never
  values; preserve that.
- **Git safety.** Never commit `.env` / `.env.local` (both gitignored). Example
  files must stay placeholder-only. If a secret is ever committed, rotate it (it
  is compromised regardless of later removal).
- **Secret rotation.** `ANTHROPIC_API_KEY`, `SMTP_*` — rotate at the provider and
  update Render, then redeploy. `JWT_SECRET_KEY` — rotating it invalidates **all**
  tokens (every user re-authenticates); a single user can be revoked instead via
  the per-user token epoch (see [operations-runbook.md → Rotate secrets](operations-runbook.md#rotate-secrets)).
- **Principle of least privilege.** Scope the Anthropic key and SMTP account to
  what NeuraEvo needs. The database has no public ingress (`ipAllowList: []`) and
  is reachable only from Render services. `NEXT_PUBLIC_*` values are world-readable
  by design — never place anything sensitive behind that prefix.

## 8. Local development

Both stacks bootstrap from the committed example files:

```bash
# Backend
cp backend/.env.example backend/.env
# adjust DATABASE_URL, JWT_SECRET_KEY, ANTHROPIC_API_KEY as needed

# Frontend
cp frontend/.env.example frontend/.env.local
# NEXT_PUBLIC_API_BASE_URL defaults to http://localhost:8000/api/v1
```

Defaults are development-friendly (`ENVIRONMENT=development`, `CORS_ORIGINS=*`,
`EMAIL_PROVIDER=console`, adapters `backend`), so the stack runs with minimal
edits. Full setup and run commands: [README → Getting started](../README.md#getting-started).

## 9. Troubleshooting

Configuration-specific failures (the full incident set is in
[operations-runbook.md → Incident playbooks](operations-runbook.md#incident-playbooks)):

| Symptom | Likely cause | Resolution |
|---|---|---|
| Backend won't start in production | `CORS_ORIGINS` is `*`, or `JWT_SECRET_KEY` is the dev default (fail-fast) | Set explicit `CORS_ORIGINS`; ensure `JWT_SECRET_KEY` is set (Blueprint `generateValue`). |
| Backend can't reach the database | `DATABASE_URL` unset, or a manual shell has the un-rewritten `postgresql://` | Confirm `fromDatabase` wiring; in a shell export `postgresql+psycopg://…` before running Alembic. |
| Frontend can't reach the backend | `NEXT_PUBLIC_API_BASE_URL` wrong or not rebuilt after change | Set the correct backend URL and **rebuild** the frontend; ensure it is in `CORS_ORIGINS`. |
| Browser CORS errors | Frontend origin missing from `CORS_ORIGINS` | Add the exact origin and redeploy the backend. |
| AI features fail / 401 from provider | `ANTHROPIC_API_KEY` missing or invalid | Set/rotate the key in Render and redeploy. |
| Verification/reset emails never arrive | `EMAIL_PROVIDER=console` (default) | Set `EMAIL_PROVIDER=smtp` and the `SMTP_*` variables. |

## 10. Maintenance — introducing a new variable

When a new configuration value is added, keep every layer in step:

**Backend variable**
1. Add the field to `Settings` in `backend/app/core/config.py` (with a safe default where possible).
2. Document it in `backend/.env.example` — **required**: `backend/tests/test_config_documentation.py` fails otherwise.
3. If it is **operator-managed in production**, add a row to §4 of this document; if **platform-managed**, add it to §5.
4. If it must be set/generated/injected in production, add it to [`render.yaml`](../render.yaml) (`sync:false` / `generateValue` / `value` / `fromDatabase`).
5. If it changes the deploy story, update [deployment.md](deployment.md) and the [launch-checklist.md](launch-checklist.md).

**Frontend variable**
1. Add it to the Zod schema in `frontend/lib/env.ts` (must be `NEXT_PUBLIC_*`, non-secret).
2. Document it in `frontend/.env.example`.
3. Update §4 of this document if it is production-managed, and note the build-time-inlined caveat.

Rule of thumb: **`config.py`/`lib/env.ts` → the matching `.env.example` → this
document → `render.yaml` (if applicable) → the deployment docs.**
