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
  deployment shares a signing key.
- **The infrastructure directory is a scaffold.** `infrastructure/docker`,
  `nginx`, `render` and `monitoring` contain empty placeholder files. The
  Dockerfile fragment above is what the backend image needs, not a description of
  one that exists.
