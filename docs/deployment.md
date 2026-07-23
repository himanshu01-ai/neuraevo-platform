# Deployment & runtime dependencies

What the backend needs from the machine it runs on, and how to check it has it.

This covers the **runtime capabilities** — the six things a workflow step can
do. Five of them need nothing beyond the standard library. One, Browser, needs a
package *and* a browser binary, and the browser is a separate download that is
easy to miss.

---

## Quick start

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/python -m playwright install chromium
```

On a slim Linux image, Chromium also needs its shared libraries:

```bash
.venv/bin/python -m playwright install-deps chromium
```

Then confirm what the deployment can actually run:

```bash
curl http://localhost:8000/api/v1/health/capabilities
```

---

## Capability requirements

| Capability | Python packages | Binaries | Env vars | Credentials | OS |
|---|---|---|---|---|---|
| Python | — | — | — | — | — |
| Filesystem | — | — | — | — | writable temp dir |
| Email | — | — | — | — | writable temp dir |
| Calendar | — | — | — | — | writable temp dir |
| GitHub | — | — | — | — | writable temp dir |
| **Browser** | **playwright** | **Chromium** | — | — | Chromium's shared libraries on Linux |

Three things about that table are worth stating plainly, because each is easy to
assume the other way:

- **No runtime capability reads an environment variable or holds a credential.**
  The Email capability opens no SMTP or IMAP connection — it composes and files
  mail in a local workspace. The `SMTP_*` settings in `core/config.py` belong to
  *account* email (verification, password reset), which is a different subsystem.
  The GitHub capability works on local repositories, not the GitHub API, so no
  access token is involved.
- **The Python capability runs code in-process** through `exec` with restricted
  builtins and an import allowlist — no subprocess, no sockets. See
  [optional libraries](#optional-libraries-for-python-steps) below.
- **Browser is the only capability that can be unavailable.** The other five
  cannot fail to be installed, because there is nothing to install.

---

## Browser: the two-step install

`pip install playwright` gives you the client library. It does **not** give you a
browser. A deployment that stops there looks correct — the package imports, the
service starts, the capability is registered — and then every Browser step fails
at the moment it tries to open a page.

So there are two steps, and both must run:

```bash
pip install -r requirements.txt          # 1. the library
python -m playwright install chromium    # 2. the browser (~150 MB)
```

In a Dockerfile, both belong in the image, not in an entrypoint:

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m playwright install --with-deps chromium
```

`--with-deps` installs the system libraries Chromium needs, which a slim base
image will not have.

### If Browser is not wanted

Browser support is optional. A deployment that never runs Browser steps can skip
the `playwright install` and leave the package uninstalled; everything else
works, and the service will:

- log a warning at startup naming the capability and what to install,
- report `unavailable` for it at `/health/capabilities`,
- fail any Browser step with *"The Browser capability requires Playwright, which
  isn't installed…"* rather than `No module named 'playwright'`.

Nothing is silently ignored, and nothing else is affected.

---

## Optional libraries for Python steps

The Python capability offers four libraries to the code a step runs, when they
happen to be installed: `numpy`, `pandas`, `openpyxl` and `matplotlib`.

They are **not** in `requirements.txt`, and that is deliberate — they are
conveniences for authored code, not requirements of the capability, and together
they are a large addition to an image that most deployments will not use. The
capability itself runs without them.

The consequence is worth stating: a Python step whose code does `import pandas`
will fail on a deployment that has not installed it, and the failure appears in
the step's `stderr`, not at startup. If your workflows use them, add them to the
image:

```bash
pip install numpy pandas openpyxl matplotlib
```

Unlike Browser, this is not reported by `/health/capabilities`: what a step's own
code imports is a property of that workflow, not of the capability.

---

## Checking a deployment

### At startup

The service reports its capabilities in the boot log:

```
Runtime capabilities ready (6/6): python, filesystem, email, calendar, github, browser
```

and warns per capability when one is not:

```
Runtime capability 'browser' is unavailable. Requires playwright, which is not
installed. Install it with `pip install -r requirements.txt`, then download the
browser with `python -m playwright install chromium`.
```

**A missing capability never stops the service from starting.** An optional
feature that was not installed should degrade that feature, not take the API
down with it.

### Over HTTP

`GET /api/v1/health/capabilities` — no authentication, since an operator
checking a deployment has no account on it.

```json
{
  "status": "degraded",
  "available_count": 5,
  "total_count": 6,
  "capabilities": [
    {
      "capability": "browser",
      "status": "unavailable",
      "detail": "Requires playwright, which is not installed.",
      "remedy": "Install it with `pip install -r requirements.txt`, then download the browser with `python -m playwright install chromium`.",
      "required_packages": ["playwright"],
      "required_binaries": ["chromium"]
    }
  ]
}
```

The three statuses:

| Status | Meaning |
|---|---|
| `available` | Everything it needs is present. |
| `unavailable` | A required package is missing; it cannot run at all. |
| `misconfigured` | The package is installed but its browser is not — the case that otherwise looks fine until a step runs. |

`status: "degraded"` is not an error. A deployment that never intends to run
Browser steps is working as configured; the endpoint reports what is true rather
than judging it.

The report is **answered once and remembered**, because asking Playwright where
its browser lives starts its driver process and costs seconds. Install something
new and restart the service to see it reflected — which a newly installed Python
package would require anyway.

`GET /api/v1/health` is unchanged and stays a constant-time liveness probe; the
capability audit is deliberately on its own path so liveness checks stay cheap.

Neither endpoint reports a filesystem path, a version, or an environment value.

---

## Environment variables

None are needed by the runtime capabilities. The service as a whole reads the
settings in `backend/app/core/config.py`; `backend/.env.example` lists the ones a
deployment normally sets:

| Variable | Needed for |
|---|---|
| `DATABASE_URL` | PostgreSQL connection. Required. |
| `JWT_SECRET_KEY` | Signing access tokens. **Required in production** — the default is a development value. |
| `ANTHROPIC_API_KEY` | Blueprint and conversation generation. |
| `QDRANT_URL`, `QDRANT_API_KEY` | Vector storage. |
| `SMTP_*`, `EMAIL_*` | Account email: verification and password reset. Not the Email capability. |
| `CORS_ORIGINS` | Defaults to `*`; narrow this in production. |
| `PLAYWRIGHT_BROWSERS_PATH` | Optional. Where Playwright looks for browsers, if not the default location. |

---

## Known deployment risks

- **Capability workspaces are temporary.** Filesystem, Email, Calendar and
  GitHub write beneath the system temp directory (`neuraevo_*`). On a container
  or a platform with an ephemeral filesystem, everything a workflow wrote is
  gone on restart, and two instances behind a load balancer do not share it.
  Anything meant to outlive a run needs durable storage, which these capabilities
  do not currently have.
- **Chromium is large.** Roughly 150 MB on top of the image, plus its shared
  libraries. Budget for it, or leave Browser out deliberately.
- **`JWT_SECRET_KEY` defaults to a development value.** Set it, or every
  deployment shares a signing key. The Render Blueprint generates one
  automatically (`generateValue: true`).

The rest of this document is the production deployment itself.

---

# Production deployment

The runtime-capability notes above are about what a single backend process can
*do*. This section is about *running the platform* — the services, how they fit
together, and how to deploy, configure, and roll them back.

**Documentation set:** this is the deployment guide. The
[environment configuration](environment.md) reference covers every variable and
who owns it. Before go-live, work through the
[production launch checklist](launch-checklist.md); once you are live, the
[operations runbook](operations-runbook.md) covers routine operations and
incident response.

## Architecture

NeuraEvo is a split deployment of two independently shippable units plus a
database:

| Component | Host | Defined by |
|---|---|---|
| Backend API (FastAPI/uvicorn) | Render — Docker web service | `infrastructure/docker/backend.Dockerfile`, `render.yaml` |
| PostgreSQL (vanilla) | Render — managed database | `render.yaml` |
| Frontend (Next.js 15 SSR) | Vercel (recommended) | Vercel project; or `infrastructure/docker/frontend.Dockerfile` to self-host |

The browser talks to the frontend, and — because the API base URL is a public,
client-inlined value (`NEXT_PUBLIC_API_BASE_URL`) — directly to the backend. The
backend is the only thing that talks to Postgres.

**Why this shape** (every piece is derived from the code):

- **No Nginx / Prometheus / Grafana / Redis / message broker / worker.** The
  backend is one stateless FastAPI app: no `/metrics` endpoint, no background
  worker process, and no scheduler (the `scheduler` service module is a pure,
  timer-free planning model — no threads, no cron). The platform provides TLS,
  routing, and metrics.
- **Vanilla PostgreSQL.** No `pgvector` column or Qdrant call exists at runtime;
  the schema is the 12 Alembic migrations under `backend/alembic/versions/`.
- **No object storage.** Nothing uses Supabase Storage or S3.
- **Single instance.** The auth/AI rate limiter and the workflow runtime keep
  per-process in-memory state. Running more than one instance — or more than one
  uvicorn worker — would split it, so `render.yaml` pins `numInstances: 1` and a
  single worker. This is the first constraint to lift (via externalised state) if
  you ever need to scale out.

## Backend on Render

`render.yaml` (at the repository root, per Render's discovery convention) is a
Blueprint: connect the repo in the Render dashboard (**New → Blueprint**) or run
`render blueprint launch`. It creates:

- `neuraevo-db` — managed PostgreSQL 18.
- `neuraevo-api` — the backend, built from `backend.Dockerfile`.

On each deploy the container entrypoint (`backend/docker-entrypoint.sh`):

1. rewrites a `postgresql://` connection string to `postgresql+psycopg://` so it
   uses psycopg v3 (the installed driver);
2. runs `alembic upgrade head` (idempotent);
3. `exec`s uvicorn on `$PORT`.

Render marks the service live once `GET /api/v1/health` returns `200`.

### Required environment variables

The Blueprint wires these; the ones marked **set** must be provided in the Render
dashboard before the first deploy (the app fails fast in production without them):

| Variable | Source in `render.yaml` | Notes |
|---|---|---|
| `DATABASE_URL` | `fromDatabase` (auto) | Injected from `neuraevo-db`. |
| `ENVIRONMENT` | `value: production` | Enables the production security gates. |
| `JWT_SECRET_KEY` | `generateValue` (auto) | Strong secret generated once by Render. |
| `CORS_ORIGINS` | **set** (`sync: false`) | Explicit frontend origin(s). Production refuses `*`. |
| `ANTHROPIC_API_KEY` | **set** (`sync: false`) | Required for AI generation. |
| `FRONTEND_BASE_URL` | **set** (`sync: false`) | Public frontend URL, used in email links. |

Every other setting in `backend/app/core/config.py` has a safe default and is
documented in `backend/.env.example`.

## Frontend on Vercel

Vercel is the recommended host — it builds and serves Next.js natively and makes
the build-time public env var trivial:

1. Import the repo into Vercel; set the project root to `frontend/`.
2. Set `NEXT_PUBLIC_API_BASE_URL` to the backend URL, e.g.
   `https://api.neuraevo.dev/api/v1`. (`NEXT_PUBLIC_*` values are inlined
   at build time, so this must be set before the build.)
3. Deploy. Optionally set the other `NEXT_PUBLIC_*_ADAPTER` switches from
   `frontend/.env.example` — all default to `backend`.

**Self-hosting alternative.** To avoid a second vendor, build
`infrastructure/docker/frontend.Dockerfile` and run it on any container platform
(including Render as a second Docker service), passing the API URL as a build arg:

```bash
docker build -f infrastructure/docker/frontend.Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://<api-host>/api/v1 ./frontend
```

Set `CORS_ORIGINS` on the backend to the resulting frontend origin.

## Deploy workflow

1. **First deploy:** launch the Blueprint → set the three `sync: false` backend
   variables → deploy. The database migrates automatically on container start.
2. **Frontend:** deploy to Vercel with `NEXT_PUBLIC_API_BASE_URL` pointing at the
   backend, then set the backend's `CORS_ORIGINS` to the frontend origin.
3. **Subsequent deploys:** push to the tracked branch. `autoDeploy` rebuilds the
   backend and applies any new migrations via the entrypoint; Vercel rebuilds the
   frontend.

## Rollback

- **Backend:** use Render's **Rollback** to redeploy a previous image. Note that
  Alembic migrations are **not** auto-reversed — a rollback that must also revert
  a schema change needs `alembic downgrade` run against the database (all 12
  migrations define `downgrade()`). Prefer forward-fixes; treat destructive
  migrations with care.
- **Frontend:** Vercel keeps immutable deployments — promote a previous one
  instantly. It has no database coupling.

## Operational notes

- **Health:** `GET /api/v1/health` (liveness, constant-time). `GET
  /api/v1/health/capabilities` reports which runtime capabilities the host can run.
- **Logs:** the app logs one structured access line per request with a correlation
  id (`X-Request-ID`, echoed on every response). Use Render's log stream.
- **Migrations block startup:** a failing migration fails the deploy (the
  container exits before serving) rather than serving a half-migrated schema.
- **Scaling:** vertical only for now (see the single-instance constraint above).
- **Browser capability** is off by default in the image (Chromium is not
  installed); the platform reports it as `unavailable`, which is not an error.
