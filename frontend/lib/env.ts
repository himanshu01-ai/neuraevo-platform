import { z } from "zod";

/**
 * Typed, Zod-validated public environment (see docs/09-state-and-api.md).
 * Only `NEXT_PUBLIC_*` values belong here — they are inlined into the client
 * bundle at build time, so they must never carry secrets.
 *
 * Next.js replaces `process.env.NEXT_PUBLIC_*` statically, so each variable has
 * to be referenced by its full literal name (no dynamic indexing).
 */
const envSchema = z.object({
  /** Base URL of the FastAPI API, including the `/api/v1` prefix. */
  NEXT_PUBLIC_API_BASE_URL: z
    .string()
    .url("NEXT_PUBLIC_API_BASE_URL must be an absolute URL")
    .default("http://localhost:8000/api/v1"),
  /**
   * Which auth adapter the app runs against. `backend` (default) talks to
   * FastAPI; `mock` keeps the Sprint 17 offline adapter for UI-only work. The
   * choice is app-wide — the two are never mixed within a session.
   */
  NEXT_PUBLIC_AUTH_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
  /**
   * Which employees adapter the app runs against. `backend` (default) talks to
   * FastAPI; `mock` keeps the Sprint 17.6 offline adapter for UI-only work.
   */
  NEXT_PUBLIC_EMPLOYEES_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
  /**
   * Which workflows adapter the app runs against. `backend` (default) talks to
   * FastAPI; `mock` keeps the Sprint 17.5 offline adapter for UI-only work.
   */
  NEXT_PUBLIC_WORKFLOWS_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
});

const parsed = envSchema.safeParse({
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  NEXT_PUBLIC_AUTH_ADAPTER: process.env.NEXT_PUBLIC_AUTH_ADAPTER,
  NEXT_PUBLIC_EMPLOYEES_ADAPTER: process.env.NEXT_PUBLIC_EMPLOYEES_ADAPTER,
  NEXT_PUBLIC_WORKFLOWS_ADAPTER: process.env.NEXT_PUBLIC_WORKFLOWS_ADAPTER,
});

if (!parsed.success) {
  throw new Error(
    "Invalid public environment configuration:\n" +
      parsed.error.issues.map((i) => `  - ${i.path.join(".")}: ${i.message}`).join("\n"),
  );
}

export const env = parsed.data;

/** API base URL with any trailing slash removed, so path joins stay predictable. */
export const apiBaseUrl = env.NEXT_PUBLIC_API_BASE_URL.replace(/\/+$/, "");
