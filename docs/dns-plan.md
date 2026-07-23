# Production DNS plan

The DNS, TLS, and email-authentication plan for NeuraEvo's approved production
domains. Planning only — this document creates no records and connects no
platforms. Values that a platform generates when a custom domain is added are
shown as `<placeholders>`; fill them from the platform dashboard at deploy time.

**Documentation set:**
[deployment guide](deployment.md) · [environment configuration](environment.md) ·
[launch checklist](launch-checklist.md) · [operations runbook](operations-runbook.md) ·
**DNS plan** (this doc).

---

## 1. Domain overview

Canonical production architecture (see [environment.md → Environment architecture](environment.md#2-environment-architecture)):

| Element | Host | Domain | TLS provided by |
|---|---|---|---|
| Frontend | Vercel | `https://neuraevo.dev` | Vercel |
| Backend API | Render | `https://api.neuraevo.dev` (base `…/api/v1`) | Render |
| Email sender | SMTP provider (TBD) | `no-reply@neuraevo.dev` | — |
| **Authoritative DNS** | **Cloudflare** | zone `neuraevo.dev` | edge cert (if proxied) |

Cloudflare owns the `neuraevo.dev` zone and points names at Vercel and Render;
it does not host the application. Each platform provisions its own certificate
for its hostname.

## 2. Required DNS records

Create these in the Cloudflare `neuraevo.dev` zone. The targets marked
`<…>` are **deployment-generated** — take the exact value Vercel/Render shows
after you add the custom domain (§6). Proxy status is **DNS only** (grey cloud)
during provisioning so each platform can validate the domain and issue its cert;
proxying can be enabled later (§5).

| Type | Name | Value / Target | Proxy | TTL | Purpose |
|---|---|---|---|---|---|
| A *or* CNAME | `neuraevo.dev` (apex) | `<vercel-apex-target>` (Vercel's apex IP, or CNAME via Cloudflare flattening) | DNS only | Auto | Frontend apex → Vercel |
| CNAME | `www` | `<vercel-dns-target>` (or a redirect to the apex) | DNS only | Auto | `www` → apex (optional) |
| CNAME | `api` | `<render-cname-target>` (the `*.onrender.com` host Render shows) | DNS only | Auto | Backend API → Render |
| TXT | `<vercel-verify-name>` / `<render-verify-name>` | `<platform-verification-token>` | n/a | Auto | Domain-ownership verification, **only if** the platform requests it |
| TXT / CNAME | *(email — see §4)* | *(SPF / DKIM / DMARC)* | DNS only | Auto | Email authentication |

Notes:
- **Apex + Cloudflare:** the apex `neuraevo.dev` cannot be a plain CNAME, but
  Cloudflare's CNAME flattening lets you enter a CNAME at the apex, or use the A
  record value Vercel supplies. Use whichever the Vercel dashboard instructs.
- Do **not** guess the `*.onrender.com` / Vercel targets — they are unique per
  service and appear only after the custom domain is added.

## 3. Cloudflare ownership and responsibilities

Cloudflare is the single authoritative DNS provider for `neuraevo.dev`. It owns:

- **Records** — the apex, `www`, `api`, and all email records above.
- **Proxy mode** — grey (DNS only) vs orange (proxied) per record (§5).
- **SSL/TLS mode** — the zone-level encryption mode when proxying (§5).
- **CAA records** — if present, they must permit the CA that Vercel/Render use
  (Let's Encrypt), or DNSSEC/CAA will block certificate issuance.
- **DNSSEC** — optional; if enabled, complete the DS-record step at the registrar.

Cloudflare does **not** run the app, terminate application logic, or hold app
secrets. It routes DNS (and, if proxied, edge traffic) only. Application config
lives with Render/Vercel — see [environment.md → Platform-managed variables](environment.md#5-platform-managed-variables).

## 4. Email DNS requirements

NeuraEvo only **sends** transactional mail (verification, password reset) as
`no-reply@neuraevo.dev` via an SMTP provider (`EMAIL_PROVIDER=smtp`; see
[environment.md → Production-managed variables](environment.md#4-production-managed-variables)).
The provider is **not yet selected**, so the values below are placeholders — the
provider's dashboard supplies the exact records once chosen.

| Purpose | Type | Name | Value (placeholder) | Notes |
|---|---|---|---|---|
| **SPF** | TXT | `neuraevo.dev` | `v=spf1 include:<provider-spf-include> ~all` | One SPF record only; merge includes if adding others. |
| **DKIM** | CNAME or TXT | `<dkim-selector>._domainkey` | `<provider-dkim-target>` | Provider gives the selector + target/key. |
| **DMARC** | TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:dmarc@neuraevo.dev; fo=1` | Start at `p=none` (monitor), then tighten to `quarantine`/`reject`. |
| **MX** | MX | `neuraevo.dev` | `<provider-mx-host>` (priority 10) | **Only if inbound mail is needed** (e.g. to receive bounces / DMARC `rua`). NeuraEvo sends only, so MX may be omitted; if omitted, use an external mailbox for `rua`/replies. |

Sending domain is the apex `neuraevo.dev` (matches the sender address). Do not
create a wildcard SPF; keep exactly one SPF TXT record.

## 5. SSL/TLS strategy

- **Vercel** auto-provisions and renews a certificate for `neuraevo.dev` (and
  `www`) once the DNS records resolve to it.
- **Render** auto-provisions and renews a certificate for `api.neuraevo.dev`
  once the `api` CNAME resolves.
- **Provisioning phase — DNS only.** Keep the Vercel/Render records unproxied
  (grey cloud) until both certificates are issued, so the platforms can complete
  ACME/HTTP validation. This is the reliable default.
- **Optional proxying — Full (strict).** If you later enable Cloudflare's proxy
  (orange cloud), set the zone **SSL/TLS mode to Full (strict)** so Cloudflare
  validates the origin's real certificate. **Never use Flexible** — it terminates
  HTTPS at the edge and talks HTTP to the origin, which causes redirect loops and
  breaks the backend's HTTPS detection.
- **HSTS** is emitted by the backend in production over HTTPS (it honors
  `X-Forwarded-Proto`, so it works behind a proxy) — see
  [environment.md → Security guidelines](environment.md#7-security-guidelines).
  Do not also enable a conflicting Cloudflare HSTS policy without coordinating
  `max-age`/`includeSubDomains`.
- **CAA:** if any CAA record exists on the zone, ensure it allows `letsencrypt.org`
  (and any CA the platforms use) or certificate issuance will fail.

## 6. Production deployment sequence

DNS-specific order; the full deploy flow is in
[deployment.md → Deploy workflow](deployment.md#deploy-workflow) and the env-var
order is in [environment.md → Deployment order](environment.md#6-deployment-order).

1. **Add the custom domain in Vercel** (`neuraevo.dev`, and `www` if wanted).
   Record the apex/`www` targets and any verification TXT it shows.
2. **Add the custom domain in Render** (`api.neuraevo.dev`). Record the
   `*.onrender.com` CNAME target and any verification TXT.
3. **Create the records in Cloudflare** (§2) with those exact targets, **DNS only**.
4. **Wait** for propagation and for Vercel/Render to issue certificates.
5. **Set the URL environment variables** and rebuild the frontend:
   `NEXT_PUBLIC_API_BASE_URL=https://api.neuraevo.dev/api/v1`,
   `CORS_ORIGINS=https://neuraevo.dev`, `FRONTEND_BASE_URL=https://neuraevo.dev`
   (see [environment.md](environment.md#4-production-managed-variables)).
6. **Select the email provider** and add its SPF/DKIM/DMARC records (§4); set
   `EMAIL_PROVIDER=smtp` and the `SMTP_*` vars.
7. **Verify** with §7, then optionally enable proxying (§5).

## 7. DNS verification checklist

- [ ] `neuraevo.dev` and `api.neuraevo.dev` resolve to the intended targets (`dig +short neuraevo.dev`, `dig +short api.neuraevo.dev`).
- [ ] `www.neuraevo.dev` resolves/redirects as intended (if configured).
- [ ] Valid TLS certificate served on `https://neuraevo.dev` and `https://api.neuraevo.dev` (no name mismatch, not expired).
- [ ] `GET https://api.neuraevo.dev/api/v1/health` returns `200`.
- [ ] The frontend loads over HTTPS at `https://neuraevo.dev` and reaches the API (no CORS error — `CORS_ORIGINS` includes `https://neuraevo.dev`).
- [ ] Response over HTTPS includes `Strict-Transport-Security` (production HSTS).
- [ ] Email auth passes: SPF, DKIM, and DMARC align (verify via the provider's dashboard or a mail-tester) — once a provider is selected.
- [ ] No CAA record blocks issuance; if DNSSEC is on, the registrar DS record is set.

Cross-references the HTTPS/TLS and DNS sections of the [launch checklist](launch-checklist.md).

## 8. Troubleshooting

Config-and-CORS incidents are also in
[operations-runbook.md → Incident playbooks](operations-runbook.md#incident-playbooks)
and [environment.md → Troubleshooting](environment.md#9-troubleshooting).

| Symptom | Likely cause | Resolution |
|---|---|---|
| Domain does not resolve (NXDOMAIN) | Record missing or not propagated | Confirm the Cloudflare record exists with the correct target; allow propagation; check the right zone. |
| Certificate stuck "pending" / invalid | Cloudflare proxy on before issuance, or a CAA record blocking the CA | Set the record to **DNS only** until the cert issues; ensure CAA allows Let's Encrypt. |
| `ERR_TOO_MANY_REDIRECTS` / redirect loop | Cloudflare SSL/TLS mode is **Flexible** | Switch to **Full (strict)**. |
| Apex won't accept a CNAME | Registrars reject CNAME at the apex | Use Cloudflare CNAME flattening, or the A-record value Vercel supplies. |
| Frontend loads but API calls fail (CORS) | `CORS_ORIGINS` missing `https://neuraevo.dev`, or `NEXT_PUBLIC_API_BASE_URL` wrong/not rebuilt | Set `CORS_ORIGINS` and redeploy backend; rebuild the frontend with the correct API URL. |
| API unreachable at custom domain but works on `*.onrender.com` | `api` CNAME wrong or not verified in Render | Re-check the CNAME target from Render; complete Render's domain verification. |
| Mail lands in spam / SPF fails | Missing/duplicate SPF, unaligned DKIM, or `p=none` only | Keep exactly one SPF record; add the provider's DKIM; align the sending domain; progress DMARC past `p=none`. |

---

*Planning document only. No DNS records, Cloudflare connections, or deployments
were created. All deployment-generated hostnames are placeholders.*
