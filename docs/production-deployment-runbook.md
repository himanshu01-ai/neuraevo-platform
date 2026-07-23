# Production deployment & verification runbook

The single, execution-focused guide for taking NeuraEvo to production on
`neuraevo.dev`. It is the *ordered procedure* that ties the planning documents
together; it does not repeat their detail — each step links to the authoritative
source. Documentation only.

**Documentation set:**
[deployment guide](deployment.md) · [environment configuration](environment.md) ·
[DNS plan](dns-plan.md) · [Cloudflare plan](cloudflare-plan.md) ·
[CORS & origin plan](cors-origin-plan.md) · [launch checklist](launch-checklist.md) ·
[operations runbook](operations-runbook.md) · **deployment runbook** (this doc).

> **Which doc when:** the [launch checklist](launch-checklist.md) is the go/no-go
> *gate*; **this runbook** is the *execution sequence* for the cutover; the
> [operations runbook](operations-runbook.md) is *day-2* operation and incident
> response afterwards.

---

## 1. Purpose

The one place an engineer follows, top to bottom, to deploy and verify a
production release.

- **Audience** — the engineer performing the deployment (and its reviewer).
- **Scope** — the first production cutover of the frontend (Vercel), backend +
  PostgreSQL (Render), DNS + edge (Cloudflare), and email DNS, to the approved
  domains. Re-deploys follow the same verification steps.
- **Preconditions** — the prerequisites in §2 are met, and the planning docs
  (environment / DNS / Cloudflare / CORS) have been read. Architecture reference:
  [deployment.md → Architecture](deployment.md#architecture).

## 2. Deployment prerequisites

- [ ] **Repository** — clean working tree; CI green (`.github/workflows/ci.yml`).
- [ ] **Production branch** — the intended commit is on the branch Render/Vercel deploy from.
- [ ] **Anthropic API key** — created in the Anthropic Console (for `ANTHROPIC_API_KEY`).
- [ ] **Domain ownership** — `neuraevo.dev` registered and controllable.
- [ ] **Cloudflare account** — the `neuraevo.dev` zone added (nameservers delegated).
- [ ] **Render account** — able to launch the Blueprint ([`render.yaml`](../render.yaml)).
- [ ] **Vercel account** — able to import the repo and set project env.
- [ ] **Production secrets** — gathered and ready to paste (never committed): see [cors-origin-plan.md → Environment variable mapping](cors-origin-plan.md#3-environment-variable-mapping) and [environment.md → Production-managed variables](environment.md#4-production-managed-variables).
- [ ] **Production environment files** — `.env.example` files validated (Sprint 1.1 Step 3); actual values set in the platforms, not in the repo.
- [ ] **Database backup strategy** — Render managed-Postgres backups enabled ([launch-checklist.md → Backups](launch-checklist.md#7-backups)).
- [ ] **Rollback plan** — understood before starting (see §6 and [operations-runbook.md → Rollback](operations-runbook.md#rollback)).

## 3. Deployment order

Execute in order; verify each step before the next. Details are in the linked docs.

| # | Step | Do | Reference |
|---|---|---|---|
| 1 | Prepare secrets | Have `ANTHROPIC_API_KEY` (and SMTP creds if email) ready | [cors-origin-plan §3](cors-origin-plan.md#3-environment-variable-mapping), [environment §4](environment.md#4-production-managed-variables) |
| 2 | Create Render services | Launch the Blueprint → creates `neuraevo-api` + `neuraevo-db` | [deployment → Backend on Render](deployment.md#backend-on-render) |
| 3 | Configure PostgreSQL | Provisioned by the Blueprint; `DATABASE_URL` auto-wired | [environment → Platform-managed variables](environment.md#5-platform-managed-variables) |
| 4 | Configure backend env vars | Set `CORS_ORIGINS=https://neuraevo.dev`, `FRONTEND_BASE_URL=https://neuraevo.dev`, `ANTHROPIC_API_KEY`; `ENVIRONMENT`/`JWT_SECRET_KEY` are auto | [environment §4/§5](environment.md#4-production-managed-variables), [cors-origin §3](cors-origin-plan.md#3-environment-variable-mapping) |
| 5 | Deploy backend | Deploy; the entrypoint migrates then serves | [deployment → Deploy workflow](deployment.md#deploy-workflow) |
| 6 | Verify backend health | `GET /api/v1/health` = 200 (on the Render URL pre-DNS) | §4 · [dns-plan §7](dns-plan.md#7-dns-verification-checklist) |
| 7 | Create Vercel project | Import repo, project root `frontend/` | [deployment → Frontend on Vercel](deployment.md#frontend-on-vercel) |
| 8 | Configure frontend env vars | `NEXT_PUBLIC_API_BASE_URL=https://api.neuraevo.dev/api/v1` (build-time) | [cors-origin §3](cors-origin-plan.md#3-environment-variable-mapping) |
| 9 | Deploy frontend | Build inlines the API URL | [deployment → Frontend on Vercel](deployment.md#frontend-on-vercel) |
| 10 | Configure DNS | Cloudflare apex + `api` + `www`, **DNS only** | [dns-plan §2](dns-plan.md#2-required-dns-records), [§6](dns-plan.md#6-production-deployment-sequence) |
| 11 | Configure Cloudflare | Full (strict); proxy `api`; security/caching/perf | [cloudflare-plan §8](cloudflare-plan.md#8-deployment-sequence) |
| 12 | Verify HTTPS | Valid certs on both origins | §4 |
| 13 | Verify CORS | Request from `https://neuraevo.dev` succeeds | [cors-origin §7](cors-origin-plan.md#7-verification-checklist) |
| 14 | Verify frontend | Loads over HTTPS and reaches the API | §4 / §5 |
| 15 | Verify AI endpoints | A generation call succeeds (validates the key) | §4 |
| 16 | Verify email | Trigger verify/reset; confirm delivery + SPF/DKIM/DMARC | [dns-plan §4](dns-plan.md#4-email-dns-requirements) |
| 17 | Final smoke test | Run the §5 checklist | §5 |

## 4. Verification procedures

| Area | How to verify | Reference |
|---|---|---|
| **Backend** | `curl https://api.neuraevo.dev/api/v1/health` → 200; an authenticated read works | [deployment → Operational notes](deployment.md#operational-notes) |
| **Frontend** | `https://neuraevo.dev` loads over HTTPS; no console errors | §5 |
| **Database** | A DB-touching request (login → list) succeeds — health alone does **not** prove DB connectivity | [operations → Incident playbooks](operations-runbook.md#incident-playbooks) |
| **HTTPS** | `http://` redirects to `https://`; both origins served over TLS | [cloudflare-plan §3](cloudflare-plan.md#3-ssltls-configuration) |
| **Certificates** | Valid, non-expired, correct host (no name mismatch) on both origins | [dns-plan §5](dns-plan.md#5-ssltls-strategy) |
| **DNS** | `dig +short neuraevo.dev` and `dig +short api.neuraevo.dev` resolve to the intended targets | [dns-plan → DNS verification](dns-plan.md#7-dns-verification-checklist) |
| **Cloudflare** | Proxy status per plan; `/api/*` not cached (`CF-Cache-Status: DYNAMIC`/`BYPASS`) | [cloudflare-plan → Verification](cloudflare-plan.md#9-verification-checklist) |
| **CORS** | Response `Access-Control-Allow-Origin: https://neuraevo.dev` (not `*`); OPTIONS preflight succeeds | [cors-origin → Verification](cors-origin-plan.md#7-verification-checklist) |
| **Authentication** | Cross-origin request with `Authorization: Bearer <token>` succeeds | [cors-origin § CORS policy](cors-origin-plan.md#4-cors-policy) |
| **AI endpoints** | A blueprint/conversation generation returns a result (not 401/429) | [operations → AI features failing or slow](operations-runbook.md#incident-playbooks) |
| **Email** | Verify/reset email is delivered; SPF/DKIM/DMARC align | [dns-plan → Email DNS](dns-plan.md#4-email-dns-requirements) |
| **Health endpoint** | `GET /api/v1/health` = 200 and is **not** cached | [deployment → Operational notes](deployment.md#operational-notes) |
| **Performance** | `X-Response-Time-ms` reasonable; static assets cached; Brotli/HTTP-3 negotiated | [cloudflare-plan → Performance](cloudflare-plan.md#7-performance-features) |
| **Security headers** | Present on the API (app-owned); no conflicting Cloudflare duplicates; frontend headers per decision | [cloudflare-plan → Headers](cloudflare-plan.md#6-headers) |

## 5. Smoke test checklist

- [ ] **Homepage loads** at `https://neuraevo.dev`.
- [ ] **Authentication works** — sign up / log in succeeds.
- [ ] **AI generation succeeds** — a generation request returns a result.
- [ ] **API responds** — a protected endpoint returns data (DB reachable).
- [ ] **Health endpoint** — `GET /api/v1/health` returns 200.
- [ ] **No browser console errors.**
- [ ] **No mixed-content warnings.**
- [ ] **No CORS failures** in the Network tab (preflight + request OK).
- [ ] **Security headers present** on API responses.
- [ ] **Performance acceptable** — page and API latency within expectation.
- [ ] **Email delivery works** — a verification/reset email arrives.

## 6. Rollback procedure

High-level; detailed steps in [operations-runbook.md → Rollback](operations-runbook.md#rollback) and [launch-checklist.md → Rollback plan](launch-checklist.md#11-rollback-plan).

- **Frontend** — promote the previous Vercel deployment (immutable, instant, no DB coupling).
- **Backend** — use Render **Rollback** to the previous image. Migrations are **not** auto-reversed — if a schema change must be undone, run `alembic downgrade` (see [operations → Run migrations manually](operations-runbook.md#routine-operations)).
- **DNS** — revert any changed record/proxy toggle in Cloudflare; allow propagation.
- **Cloudflare** — disable a newly added proxy/rule (return the record to DNS-only) if the edge is implicated.
- **Database considerations** — prefer forward-fixes; a destructive migration may need a restore from backup ([launch-checklist → Backups](launch-checklist.md#7-backups)). Ensure a fresh backup exists immediately before cutover.
- **Verify after rollback** — re-run the §5 smoke test against the restored version.

## 7. Post-deployment monitoring (first 24–48 hours)

Watch via Render metrics/logs and the platform dashboards (observability details:
[operations-runbook.md → Observability](operations-runbook.md#observability)):

| Signal | What to watch |
|---|---|
| Application logs | Structured access lines; trace issues by `X-Request-ID` |
| API errors | 5xx rate and any repeated handled errors |
| AI usage | Anthropic call volume/cost and `429` from the AI rate limit |
| Latency | `X-Response-Time-ms`; p95 on hot paths |
| Database health | Connections/pool saturation on the single instance |
| Memory / CPU | Render instance metrics (scale up, not out) |
| HTTP error rates | 4xx/5xx at the edge (Cloudflare) and origin |
| Email delivery | Bounce/spam rates; SPF/DKIM/DMARC pass rate |
| Security alerts | Cloudflare WAF/bot/rate-limit events |

## 8. Incident response

First actions if something breaks during or after cutover — then hand off to the
detailed playbooks in [operations-runbook.md → Incident playbooks](operations-runbook.md#incident-playbooks):

1. **Confirm scope** — is it frontend, backend, DNS/edge, or email? Check `GET /api/v1/health` and the browser Network/console.
2. **Correlate** — get the failing request's `X-Request-ID` and grep the logs.
3. **Decide** — forward-fix vs roll back (§6). Prefer rollback if user-facing and the cause is not immediately obvious.
4. **Common cases** — boot fail-fast (wildcard CORS / dev JWT secret), migration failure, DB connectivity, CORS mismatch, 429/AI upstream: each has a playbook in the operations runbook.
5. **Escalate/record** — note the timeline and the `X-Request-ID`s for the post-mortem.

## 9. Maintenance

Keep this runbook in step with the architecture. Whenever the deployment shape
changes, update the relevant planning doc **and** this runbook's order/verification:

- **Variables / secrets** → [environment.md](environment.md)
- **Domains / DNS / TLS / email** → [dns-plan.md](dns-plan.md)
- **Edge (proxy, security, caching, headers)** → [cloudflare-plan.md](cloudflare-plan.md)
- **Origins / CORS** → [cors-origin-plan.md](cors-origin-plan.md)
- **Build/serve/migrations** → [deployment.md](deployment.md)
- **Go-live gate** → [launch-checklist.md](launch-checklist.md); **day-2** → [operations-runbook.md](operations-runbook.md)

If a step's authoritative source moves, fix the cross-reference here rather than
copying the content in.

---

*Documentation only. No application code, deployment configuration, DNS, or
Cloudflare resources were created or modified.*
