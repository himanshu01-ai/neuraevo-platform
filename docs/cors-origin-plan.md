# Production CORS & origin plan

The authoritative origin policy for NeuraEvo: which origins exist, how the
browser's cross-origin rules apply to a split frontend/backend, and exactly how
CORS is configured. Documentation only — this changes no code or configuration;
it records the policy the existing implementation enforces.

**Documentation set:**
[deployment guide](deployment.md) · [environment configuration](environment.md) ·
[DNS plan](dns-plan.md) · [Cloudflare plan](cloudflare-plan.md) ·
[launch checklist](launch-checklist.md) · [operations runbook](operations-runbook.md) ·
[deployment runbook](production-deployment-runbook.md) · **CORS & origin plan** (this doc).

---

## 1. Purpose

- **Browser origin** — the tuple **scheme + host + port** (e.g. `https://neuraevo.dev`).
  Two URLs share an origin only if all three match.
- **Same-Origin Policy (SOP)** — browsers block a page from *reading* responses
  from a different origin by default. It is a browser-enforced security boundary.
- **CORS** — the server's opt-in to relax SOP for named origins, by returning
  `Access-Control-Allow-*` headers. Without them, the browser blocks the response.

NeuraEvo serves the frontend at `https://neuraevo.dev` and the API at
`https://api.neuraevo.dev` — **different origins** (different subdomains). So
*every* browser call from the app to the API is cross-origin and depends on CORS.
This makes explicit origin configuration mandatory on both sides:

- the **backend** must name the frontend origin in `CORS_ORIGINS`, and
- the **frontend** must target the exact backend origin in `NEXT_PUBLIC_API_BASE_URL`.

See [environment.md → Environment architecture](environment.md#2-environment-architecture).

## 2. Production origin architecture

| Component | URL | Purpose | Platform |
|---|---|---|---|
| Frontend | `https://neuraevo.dev` | The web app (browser origin) | Vercel |
| Backend | `https://api.neuraevo.dev` | The API host | Render |
| API | `https://api.neuraevo.dev/api/v1` | Versioned API base | Render |
| Email | `no-reply@neuraevo.dev` | Transactional sender | SMTP provider (TBD) |
| DNS Provider | `neuraevo.dev` zone | Authoritative DNS + edge | Cloudflare |

## 3. Environment variable mapping

Reuses the Step 1.1 inventory / matrix (see [environment.md → Production-managed variables](environment.md#4-production-managed-variables)):

| Variable | Value | Platform | Secret? | Owner | Purpose |
|---|---|---|---|---|---|
| `FRONTEND_BASE_URL` | `https://neuraevo.dev` | Render | No | Backend | Base URL for links in verification/reset email |
| `CORS_ORIGINS` | `https://neuraevo.dev` | Render | No | Backend | The exact browser origin(s) the API accepts |
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.neuraevo.dev/api/v1` | Vercel | No (public, build-time) | Frontend | The API origin the browser calls |
| `EMAIL_FROM_ADDRESS` | `no-reply@neuraevo.dev` | Render | No | Backend | Transactional sender address |

## 4. CORS policy

The backend applies CORS in `app/main.py` (Starlette `CORSMiddleware`). The effective production configuration:

| Aspect | Production value | Notes |
|---|---|---|
| **Allowed origins** | `https://neuraevo.dev` | Exact match (scheme+host). From `CORS_ORIGINS`. |
| **Development origins** | `http://localhost:3000` | The dev default is `*` (wildcard), never used in production. |
| **Credential support** | **Enabled** in production | `Access-Control-Allow-Credentials: true` is sent **only** when origins are explicit; it is **disabled** when the origin list is wildcard (dev). |
| **Allowed methods** | All (`*`) | `GET, POST, PATCH, PUT, DELETE, OPTIONS`. |
| **Allowed headers** | All (`*`) | Includes `Authorization` and `Content-Type`. |
| **Exposed headers** | `X-Request-ID`, `X-Response-Time-ms` | Readable by the browser for correlation/timing. |
| **Preflight (OPTIONS)** | Handled automatically | Starlette answers preflight with the allow-origin/methods/headers above. |

**Auth mechanism:** the frontend authenticates with a **Bearer token in the
`Authorization` header** (`Authorization: Bearer <token>`), not cookies — the
`fetch` client does not send credentials (`credentials: 'include'` is not used).
Cross-origin auth therefore works because `Authorization` is an allowed header;
cookies are not part of the flow. (`Access-Control-Allow-Credentials: true` is
still emitted in production because origins are explicit.)

**Why wildcard origins are prohibited in production:**

1. **The app refuses to boot** with `*` outside development (production fail-fast — see [environment.md → Security guidelines](environment.md#7-security-guidelines)).
2. **The CORS spec forbids** `Access-Control-Allow-Origin: *` together with credentials; a real credentialed API must name explicit origins. This is exactly why the app disables credentials under a wildcard and enables them only with explicit origins.
3. **Security** — a wildcard would let any website call the API on a user's behalf.

## 5. Development vs production

| Aspect | Development | Production |
|---|---|---|
| Frontend URL | `http://localhost:3000` | `https://neuraevo.dev` |
| Backend URL | `http://localhost:8000` | `https://api.neuraevo.dev` |
| API URL | `http://localhost:8000/api/v1` | `https://api.neuraevo.dev/api/v1` |
| CORS | `*` (wildcard, credentials **off**) | `https://neuraevo.dev` (explicit, credentials **on**) |
| HTTPS | No (plain http) | Yes (Vercel/Render TLS; HSTS) |
| Environment variables | `ENVIRONMENT=development`, defaults | `ENVIRONMENT=production`, explicit values (§3) |

## 6. Deployment sequence

Because the production domains are already finalized, the API origin
(`https://api.neuraevo.dev`) is known ahead of time, so the frontend can be built
with the correct `NEXT_PUBLIC_API_BASE_URL` without waiting for a generated URL.
Recommended order (aligns with [environment.md → Deployment order](environment.md#6-deployment-order) and [deployment.md → Deploy workflow](deployment.md#deploy-workflow)):

1. **Configure Render environment variables** — `CORS_ORIGINS=https://neuraevo.dev`, `FRONTEND_BASE_URL=https://neuraevo.dev`, plus the secrets.
2. **Deploy backend** — migrations run, API serves at its origin.
3. **Configure Vercel environment variables** — `NEXT_PUBLIC_API_BASE_URL=https://api.neuraevo.dev/api/v1`.
4. **Deploy frontend** — the API URL is inlined at build time.
5. **Configure DNS** — point `neuraevo.dev`/`api.neuraevo.dev` at the platforms ([dns-plan.md → Required DNS records](dns-plan.md#2-required-dns-records)).
6. **Verify HTTPS** — valid certs on both origins.
7. **Verify CORS** — a browser request from `https://neuraevo.dev` succeeds.
8. **Verify API** — health + an authenticated round-trip.

**Why this order:** the backend must already accept the frontend origin (step 1)
before the frontend starts calling it (step 4), and DNS/HTTPS must be live (steps
5–6) before CORS can be validated end-to-end (step 7). Setting `CORS_ORIGINS` last
would cause the first frontend calls to be blocked.

## 7. Verification checklist

- [ ] **Frontend origin** — the app is served from `https://neuraevo.dev` (exact scheme/host).
- [ ] **API origin** — requests target `https://api.neuraevo.dev/api/v1` (matches `NEXT_PUBLIC_API_BASE_URL`).
- [ ] **CORS** — API responses include `Access-Control-Allow-Origin: https://neuraevo.dev` (not `*`).
- [ ] **OPTIONS requests** — preflight returns success with `Access-Control-Allow-Methods`/`-Headers`.
- [ ] **Authentication** — a cross-origin request with `Authorization: Bearer <token>` succeeds; `Access-Control-Allow-Credentials: true` present.
- [ ] **Cookies** — N/A: auth is header-based (Bearer), no auth cookies are set or required.
- [ ] **Health endpoint** — `GET https://api.neuraevo.dev/api/v1/health` returns 200.
- [ ] **Browser console** — no CORS or mixed-content errors.
- [ ] **Network tab** — the preflight (OPTIONS) and the actual request both succeed; response headers look correct.
- [ ] **Environment variables** — `CORS_ORIGINS`, `FRONTEND_BASE_URL` (Render) and `NEXT_PUBLIC_API_BASE_URL` (Vercel) hold the §3 values.

## 8. Troubleshooting

Also see [operations-runbook.md → Incident playbooks](operations-runbook.md#incident-playbooks) and [environment.md → Troubleshooting](environment.md#9-troubleshooting).

| Issue | Likely cause | Resolution |
|---|---|---|
| **Wrong `FRONTEND_BASE_URL`** | Email links point at the wrong/localhost host | Set to `https://neuraevo.dev`, redeploy backend. |
| **Wrong `CORS_ORIGINS`** | Value omits the frontend origin, has a trailing slash, or uses `http`/`www` | Use the exact origin `https://neuraevo.dev` (no trailing slash, no path); redeploy. Note: `*` in production blocks boot. |
| **Wrong `NEXT_PUBLIC_API_BASE_URL`** | Points at the wrong host, or was changed without rebuilding | Set to `https://api.neuraevo.dev/api/v1` and **rebuild** the frontend (build-time inlined). |
| **Mixed content** | `https` frontend calling an `http` API URL | Ensure the API URL uses `https`. |
| **Preflight failures** | OPTIONS blocked upstream, or an edge rule stripped CORS headers | The app allows all methods/headers; check that no Cloudflare/proxy rule rewrites or removes CORS headers ([cloudflare-plan.md → Headers](cloudflare-plan.md#6-headers)). |
| **Origin mismatch** | apex vs `www`, `http` vs `https`, or trailing slash differences | Origins must match exactly; redirect `www`→apex; keep everything `https`. |
| **Environment variable mistakes** | Typo, wrong platform, or not applied | Re-check §3; Render vars need a redeploy, Vercel `NEXT_PUBLIC_*` need a rebuild. |
| **Browser cache** | Cached preflight (`Access-Control-Max-Age`) or cached redirect after a config change | Hard-reload / clear site data; retry in a private window. |

## 9. Maintenance

When origins change, update configuration **and** the docs together.

| Change | Action | Docs to update |
|---|---|---|
| **New frontend domain** | Append it to `CORS_ORIGINS` (comma-separated); update the canonical domain if it replaces `neuraevo.dev` | `environment.md`, `dns-plan.md` (records for the new host), `cloudflare-plan.md` (proxy/records), `deployment.md`, `render.yaml` comments |
| **Staging environment introduced** | Give staging its own `ENVIRONMENT`, `CORS_ORIGINS` (staging frontend origin), and a staging `NEXT_PUBLIC_API_BASE_URL` build | `environment.md`, `dns-plan.md`, `deployment.md` |
| **API domain changes** | Update `NEXT_PUBLIC_API_BASE_URL` and **rebuild** the frontend; update the `api` DNS/proxy records | `environment.md`, `dns-plan.md`, `cloudflare-plan.md`, `render.yaml` comments |
| **A new origin needs CORS access** | Append the exact origin to `CORS_ORIGINS` (never widen to `*`) | `environment.md`, this document |

General rule (mirrors the Maintenance section of [environment.md](environment.md)): change the value in the platform, then keep the origin docs in this set consistent — `environment.md` (variables), `dns-plan.md` (records), `cloudflare-plan.md` (edge), `deployment.md` (workflow), and `render.yaml` comments where applicable.

---

*Documentation only. No application code, deployment configuration, DNS, or
Cloudflare resources were created or modified.*
