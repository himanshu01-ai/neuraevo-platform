/** @type {import('next').NextConfig} */

// --- Security response headers (Sprint 1.3 — production security audit) ------
//
// The API origin (api.neuraevo.dev) already emits a complete security-header set
// from its FastAPI middleware; the frontend origin (neuraevo.dev), which is the
// one that actually serves HTML, previously sent none — the gap recorded in
// docs/cloudflare-plan.md §6 as "a decision to make". These headers close it in
// the application (portable across Vercel or the self-hosted container), rather
// than relying on an edge Transform Rule that only exists once Cloudflare proxies
// the frontend.
//
// The CSP is HTML-appropriate (NOT the API's `default-src 'none'`) and tuned to
// what this app genuinely does: Next's App Router injects inline hydration/stream
// scripts (`'unsafe-inline'`); framer-motion and Next inject inline styles;
// next/image and the react-three-fiber canvas use data:/blob: images; three.js
// and the workflow export use blob: workers/URLs; and the browser calls the API
// origin (connect-src). Fonts are self-hosted by next/font, so `font-src 'self'`.
// The voice features use the browser-native Web Speech API, which is gated by the
// microphone permission — so Permissions-Policy keeps `microphone` enabled for
// same-origin rather than disabling it as the API does.
const isProduction = process.env.NODE_ENV === "production";

/** Origin (scheme://host[:port]) of the API base URL, for CSP `connect-src`. */
function apiConnectSource() {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!raw) return "";
  try {
    return new URL(raw).origin;
  } catch {
    // Malformed value — lib/env.ts fails the build on it anyway; degrade to none.
    return "";
  }
}

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  // Next.js App Router emits inline bootstrap/streaming scripts. No 'unsafe-eval'
  // in production (dev/HMR would need it, but CSP is production-only here).
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "media-src 'self' blob: data:",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  `connect-src 'self' ${apiConnectSource()}`.trim(),
  "upgrade-insecure-requests",
].join("; ");

// Always-safe headers (harmless in development too).
const baseSecurityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
  // Voice-first app: keep microphone available to same-origin (Web Speech API);
  // nothing here uses the camera, geolocation, USB, or payment.
  {
    key: "Permissions-Policy",
    value: "camera=(), geolocation=(), usb=(), payment=(), microphone=(self)",
  },
];

// Production-only headers: HSTS would be a footgun on http://localhost, and the
// strict CSP would block Next's dev-mode eval/HMR — so both apply only to the
// production build (Vercel and the container both run with NODE_ENV=production).
const productionSecurityHeaders = isProduction
  ? [
      {
        key: "Strict-Transport-Security",
        value: "max-age=63072000; includeSubDomains",
      },
      { key: "Content-Security-Policy", value: contentSecurityPolicy },
    ]
  : [];

const securityHeaders = [...baseSecurityHeaders, ...productionSecurityHeaders];

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // React Three Fiber ships ESM; transpile three ecosystem packages.
  transpilePackages: ["three"],
  experimental: {
    // Tree-shake large icon / animation libraries by default.
    optimizePackageImports: ["lucide-react", "framer-motion"],
  },
  images: {
    formats: ["image/avif", "image/webp"],
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
