# Production Cloudflare configuration plan

The recommended Cloudflare settings for NeuraEvo's production edge, assuming
Cloudflare (DNS + edge), Vercel (frontend), Render (backend), and HTTPS
everywhere. Planning only — this document configures nothing and connects no
domain. Until deployment, Cloudflare manages **DNS only** (records stay
unproxied); the proxied-edge settings below apply once certificates are issued.
Provider-generated values are shown as `<placeholders>`.

**Documentation set:**
[deployment guide](deployment.md) · [environment configuration](environment.md) ·
[DNS plan](dns-plan.md) · [CORS & origin plan](cors-origin-plan.md) ·
[launch checklist](launch-checklist.md) ·
[operations runbook](operations-runbook.md) · **Cloudflare plan** (this doc).

---

## 1. Purpose

Cloudflare is the authoritative DNS provider for `neuraevo.dev` and, once records
are proxied, the security/TLS/caching edge in front of the platforms. It does
**not** run the application.

| Concern | Owner |
|---|---|
| DNS zone, records, proxy toggle, edge TLS, WAF/DDoS/bot mitigation, edge rate-limiting, edge caching | **Cloudflare** |
| Serving the frontend (`neuraevo.dev`), Next.js build, its TLS cert, asset/image optimization, SSR | **Vercel** |
| Serving the backend API (`api.neuraevo.dev`), its TLS cert, **application security headers**, **CORS**, **app-level auth/AI rate limiting**, migrations, business logic | **Render (the app)** |

What stays with the platforms: the backend already emits a complete
security-header set and enforces CORS and per-user auth/AI rate limits (see
[environment.md → Security guidelines](environment.md#7-security-guidelines) and
[Platform-managed variables](environment.md#5-platform-managed-variables)). Cloudflare
should **complement**, not duplicate, these. DNS ownership and the provisioning
posture are defined in [dns-plan.md → Cloudflare ownership](dns-plan.md#3-cloudflare-ownership-and-responsibilities).

## 2. DNS proxy strategy

Provisioning first: keep every record **DNS only** until Vercel and Render have
issued their certificates ([dns-plan.md → SSL/TLS strategy](dns-plan.md#5-ssltls-strategy)).
Then apply the proxy posture below.

| Record | Recommendation | Why |
|---|---|---|
| **apex `neuraevo.dev`** (Vercel) | **DNS only** (grey) | Vercel already fronts the app with its own global CDN + TLS; proxying through Cloudflare adds a second CDN, can obscure the real client IP, and can interfere with Vercel routing/ISR. Let Vercel's edge serve directly. |
| **`api.neuraevo.dev`** (Render) | **Proxied** (orange) | Puts Cloudflare's DDoS/WAF/edge rate-limiting in front of the API — the highest-value protection for the expensive AI/auth endpoints. Requires **Full (strict)** SSL (§3). |
| **`www`** | **DNS only**, redirect to apex | With the frontend DNS-only, configure the `www → neuraevo.dev` 301 at Vercel. (A Cloudflare Redirect Rule would require proxying `www`.) |

Do not invent the Vercel/Render targets — take them from each dashboard
([dns-plan.md → Required DNS records](dns-plan.md#2-required-dns-records)).

## 3. SSL/TLS configuration

| Setting | Recommended | Notes |
|---|---|---|
| **Encryption mode** | **Full (strict)** | Validates the origin's real certificate (Vercel/Render). Set this **before** proxying `api`. |
| **Minimum TLS version** | **1.2** | Disallow TLS 1.0/1.1. |
| **TLS 1.3** | Enabled | — |
| **Automatic HTTPS Rewrites** | Enabled | Upgrades http subresource URLs. |
| **Always Use HTTPS** | Enabled | Edge redirects http→https. The app also enforces via HSTS. |
| **HTTP/2** | Enabled | — |
| **HTTP/3 (QUIC)** | Enabled | — |
| **HSTS** | App owns it on the API | The backend already emits HSTS in production over HTTPS (honors `X-Forwarded-Proto`, so it survives the proxy) — see [environment.md → Security guidelines](environment.md#7-security-guidelines). Do **not** double-set for `api`. If you want HSTS on the **frontend**, enable it once (Cloudflare or Vercel) with a matching `max-age` (63072000) and be deliberate about `includeSubDomains`/preload. |
| **Certificate Transparency Monitoring** | Enabled | Alerts on unexpected certs. |
| **CAA** | Allow the CAs in use, or none | Must permit Let's Encrypt (Vercel/Render) and Cloudflare's edge CA, or issuance fails ([dns-plan.md → SSL/TLS strategy](dns-plan.md#5-ssltls-strategy)). |

**Never use Flexible SSL.** Flexible encrypts only client↔edge and talks **plain
HTTP** edge↔origin. Because the app enforces HTTPS, the origin redirects http→https
and Cloudflare loops (`ERR_TOO_MANY_REDIRECTS`); the origin leg is unencrypted; and
the app's `X-Forwarded-Proto`/HSTS logic misreads the scheme. Always Full (strict).

## 4. Edge security

Recommended for an AI SaaS whose costliest resource is per-request Anthropic usage:

| Feature | Recommendation | For NeuraEvo |
|---|---|---|
| **Browser Integrity Check** | On | Cheap filter of malformed/abusive requests. |
| **Security Level** | Medium (raise to High under attack) | Balanced default. |
| **Bot Fight Mode** | On for the **frontend**; **not** interactive challenges on the API | The API has non-browser clients (SSR calls, future mobile) that cannot solve JS/CAPTCHA challenges — protect it with WAF + rate-limiting instead. |
| **DDoS protection** | Always on (automatic L3/4/7) | Baseline. |
| **WAF — Managed Rules** | Enable Cloudflare Managed + OWASP core ruleset | Start in **log** mode, tune to avoid false positives on the JSON API, then enforce. |
| **Challenge strategy** | Challenge suspicious **browser** traffic; avoid interactive challenges on `/api/*` | Keeps programmatic API clients working. |
| **Rate Limiting** | Edge limits on `/api/v1/auth/*` and the AI/generation endpoints | **Complements** the app's in-process `AUTH_RATE_LIMIT_*` / `AI_RATE_LIMIT_*` (which are per-process and reset on redeploy). An edge limit blocks abuse **before** it reaches the single backend instance and before it spends Anthropic budget. |

The high-value protections here are DDoS + WAF + **edge rate-limiting on the AI and
auth paths** (cost and abuse control), plus bot mitigation on the frontend.

## 5. Caching strategy

Default stance: cache static frontend assets; **never cache the API**.

| Surface | Recommendation |
|---|---|
| **Frontend** (`neuraevo.dev`) | DNS-only → Vercel's CDN caches (Next static assets immutable, SSR dynamic). If later proxied, honor Vercel's `Cache-Control`. |
| **Static assets** (`/_next/static/…`) | Cache long/immutable (Vercel already sets this; honor it). |
| **API** (`api.neuraevo.dev`, proxied) | **Bypass cache** — add a Cache Rule: do not cache `api.neuraevo.dev/*`. |
| **Dynamic endpoints** | Never cache. |
| **Auth endpoints** (`/api/v1/auth/*`) | **Never cache** (tokens/sessions). |
| **AI endpoints** (generation) | **Never cache** (per-user, non-idempotent). |
| **Health** (`/api/v1/health`) | **Never cache** (must reflect live state). |

**Never cache anything under `/api/`.** The single explicit rule "bypass cache for
`api.neuraevo.dev/*`" covers auth, AI, health, and all dynamic responses.

## 6. Headers

The backend **already owns** a complete security-header set on `api.neuraevo.dev`
(Sprint 25): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy` (`default-src
'none'` — correct for a JSON API), and HSTS (prod+HTTPS). The **frontend** (Next.js
on Vercel) currently sets **no** security response headers (its `next.config.mjs`
has no `headers()`), so those are a gap on `neuraevo.dev`.

| Header | API `api.neuraevo.dev` | Frontend `neuraevo.dev` |
|---|---|---|
| `Strict-Transport-Security` | **Application** (do not duplicate at edge) | Cloudflare **or** Vercel — currently unset |
| `X-Content-Type-Options` | **Application** (`nosniff`) | Recommend adding (edge or Next config) |
| `X-Frame-Options` | **Application** (`DENY`) | Recommend adding |
| `Referrer-Policy` | **Application** | Recommend adding |
| `Permissions-Policy` | **Application** | Recommend adding |
| `Content-Security-Policy` | **Application** (`default-src 'none'`) | **Needs an HTML-appropriate CSP** — do **not** copy the API's `none` policy; unset today |

Guidance: on the API, let the application remain the single source of these headers
(Cloudflare must not add conflicting duplicates). On the frontend, the gap can be
filled by a Cloudflare **Response Header Transform Rule** or a Next.js `headers()`
config — the latter is a code change and is **out of scope for this planning doc**;
recorded here as a decision to make.

## 7. Performance features

| Feature | Recommendation | Reason |
|---|---|---|
| **HTTP/3 (QUIC)** | Enable | Latency win, no downside. |
| **Brotli** | Enable | Helps proxied API JSON; Vercel already compresses the frontend. |
| **Compression** (gzip/brotli) | Enable | Standard. |
| **Early Hints** | Optional/cautious | Only if it doesn't conflict with Next/Vercel's own hints. |
| **Image Optimization** (Polish/Mirage) | **Disabled** | Next.js/Vercel already serve AVIF/WebP (`next.config` `images.formats`) — double-optimization is wasteful and can corrupt output. |
| **Auto Minify** (HTML/CSS/JS) | **Disabled** | `next build` already minifies with content hashes; edge minification breaks hashed bundles (and Cloudflare has deprecated it). |
| **Rocket Loader** | **Disabled** | It defers/reorders JS and **breaks React hydration** — never for a Next.js app. |

The features that stay **off** — Image Optimization, Auto Minify, Rocket Loader —
are ones the frontend build already handles; enabling Cloudflare's versions causes
conflicts and hydration bugs.

## 8. Deployment sequence

Enable features in this order, verifying after each stage (full deploy flow:
[deployment.md → Deploy workflow](deployment.md#deploy-workflow); DNS order:
[dns-plan.md → Production deployment sequence](dns-plan.md#6-production-deployment-sequence)):

1. **DNS only, records created** → verify names resolve and Vercel/Render certs issue.
2. **SSL/TLS = Full (strict)** → verify the origin certs are valid before proxying.
3. **Proxy `api` (orange)** → verify `https://api.neuraevo.dev/api/v1/health` = 200, valid cert, no redirect loop.
4. **Always Use HTTPS + Automatic HTTPS Rewrites + TLS 1.3 + min TLS 1.2 + HTTP/2/3** → verify http→https redirect and negotiated TLS version.
5. **Cache Rule: bypass `api.neuraevo.dev/*`** → verify responses show `CF-Cache-Status: DYNAMIC`/`BYPASS`.
6. **WAF Managed Rules in log mode → tune → enforce** → verify no false positives on login/AI traffic.
7. **Edge rate-limiting on auth + AI paths** → verify legitimate traffic passes, abuse gets `429`.
8. **Frontend proxy decision** (default DNS-only) → if proxied, repeat cert/cache verification.
9. **Frontend security headers** (edge Transform Rule or Next config) → verify present and the CSP does not break the app.

## 9. Verification checklist

Complements [dns-plan.md → DNS verification checklist](dns-plan.md#7-dns-verification-checklist)
and the HTTPS/TLS and DNS sections of the [launch checklist](launch-checklist.md).

- [ ] **DNS:** apex, `api`, `www` resolve to the intended targets; proxy status matches §2.
- [ ] **SSL:** encryption mode is Full (strict); min TLS 1.2; TLS 1.3 negotiated.
- [ ] **Certificates:** valid, non-expired certs on `neuraevo.dev` and `api.neuraevo.dev` (no name mismatch).
- [ ] **HTTP headers:** `http://` redirects to `https://`; security headers present (API from app; frontend per §6 decision), with no duplicates on the API.
- [ ] **Caching:** `/api/*` responses are not cached (`CF-Cache-Status: DYNAMIC`/`BYPASS`); static assets cached.
- [ ] **API:** `https://api.neuraevo.dev/api/v1/health` = 200; a protected endpoint works end-to-end (DB reachable).
- [ ] **Frontend:** `https://neuraevo.dev` loads over HTTPS and reaches the API.
- [ ] **Health endpoint:** returns 200 and is not cached.
- [ ] **Email:** SPF/DKIM/DMARC align once a provider is chosen ([dns-plan.md → Email DNS](dns-plan.md#4-email-dns-requirements)).
- [ ] **CORS:** requests from `https://neuraevo.dev` succeed; unlisted origins refused (`CORS_ORIGINS` set — [environment.md](environment.md#4-production-managed-variables)).
- [ ] **Security headers:** present on both origins with no conflicting Cloudflare duplicates on the API.

## 10. Troubleshooting

Also see [dns-plan.md → Troubleshooting](dns-plan.md#8-troubleshooting),
[operations-runbook.md → Incident playbooks](operations-runbook.md#incident-playbooks),
and [environment.md → Troubleshooting](environment.md#9-troubleshooting).

| Symptom | Likely cause | Resolution |
|---|---|---|
| **SSL mismatch** / untrusted cert | Proxying before the origin cert issued, or mode not Full (strict) | Set Full (strict); keep DNS-only until the platform cert issues. |
| **Redirect loop** (`ERR_TOO_MANY_REDIRECTS`) | SSL mode **Flexible** | Switch to Full (strict). |
| **Mixed content** | Page loads http subresources | Enable Automatic HTTPS Rewrites; fix absolute http URLs. |
| **CORS failures** | `CORS_ORIGINS` missing `https://neuraevo.dev`, or a Cloudflare rule stripped headers | Set `CORS_ORIGINS` and redeploy backend; ensure no edge rule rewrites CORS headers. |
| **Proxy issues** (wrong client IP, rate limits misfire) | App reading remote addr instead of `CF-Connecting-IP`/`X-Forwarded-For` | Use the forwarded client IP at the edge for rate rules; the app already trusts `X-Forwarded-Proto` for HTTPS. |
| **Cache issues** (stale/duplicated API data) | `/api/*` being cached | Add/repair the `api.neuraevo.dev/*` bypass Cache Rule. |
| **Certificate provisioning stuck** | Proxy on before validation, or CAA blocking the CA | DNS-only until issued; ensure CAA permits Let's Encrypt/Cloudflare. |
| **Rate limiting** (legit users get 429) | Edge limit too tight, or shared-IP clients | Loosen thresholds/scope; key on user/token where possible; combine with WAF instead of blanket limits. |
| **DNS propagation** | Record not yet global | Confirm the record in the correct zone; allow propagation; verify with `dig +short`. |

---

*Planning document only. No Cloudflare resources, DNS records, or deployments were
created or modified. All provider-generated values are placeholders.*
