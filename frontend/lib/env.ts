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
  /**
   * Which tasks adapter the app runs against. `backend` (default) talks to
   * FastAPI; `mock` keeps the Sprint 17.7 offline adapter for UI-only work.
   */
  NEXT_PUBLIC_TASKS_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
  /**
   * Which memory-integration adapter the app runs against. `backend` (default)
   * talks to the FastAPI memory-link endpoints; `mock` keeps an offline adapter
   * for UI-only work. Governs the task/workflow memory-link surface.
   */
  NEXT_PUBLIC_MEMORY_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
  /**
   * Which adapter the standalone memory *workspace* runs against. `backend`
   * (default, Sprint 23) shows the user's real memories via the Memory Engine's
   * `GET /memories`, with the workspace's richer surfaces derived from those
   * real records; `mock` keeps the Sprint 17 offline fixtures for UI-only work.
   */
  NEXT_PUBLIC_MEMORY_WORKSPACE_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
  /**
   * Which conversations adapter the app runs against. `backend` (default) talks
   * to the FastAPI Conversation Hub (text and voice turns); `mock` keeps the
   * Sprint 17.9 offline adapter for UI-only work.
   */
  NEXT_PUBLIC_CONVERSATIONS_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
  /**
   * Which collaboration adapter the notification center runs against. `backend`
   * (default) talks to the Sprint 20 Collaboration Platform (real notifications
   * raised by participant/share actions); `mock` keeps the Sprint 17.10 offline
   * fixtures for UI-only work. The participant/share/activity resource surface is
   * always backend — it is fully served by the platform.
   */
  NEXT_PUBLIC_COLLABORATION_ADAPTER: z.enum(["backend", "mock"]).default("backend"),
});

const parsed = envSchema.safeParse({
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  NEXT_PUBLIC_AUTH_ADAPTER: process.env.NEXT_PUBLIC_AUTH_ADAPTER,
  NEXT_PUBLIC_EMPLOYEES_ADAPTER: process.env.NEXT_PUBLIC_EMPLOYEES_ADAPTER,
  NEXT_PUBLIC_WORKFLOWS_ADAPTER: process.env.NEXT_PUBLIC_WORKFLOWS_ADAPTER,
  NEXT_PUBLIC_TASKS_ADAPTER: process.env.NEXT_PUBLIC_TASKS_ADAPTER,
  NEXT_PUBLIC_MEMORY_ADAPTER: process.env.NEXT_PUBLIC_MEMORY_ADAPTER,
  NEXT_PUBLIC_MEMORY_WORKSPACE_ADAPTER: process.env.NEXT_PUBLIC_MEMORY_WORKSPACE_ADAPTER,
  NEXT_PUBLIC_CONVERSATIONS_ADAPTER: process.env.NEXT_PUBLIC_CONVERSATIONS_ADAPTER,
  NEXT_PUBLIC_COLLABORATION_ADAPTER: process.env.NEXT_PUBLIC_COLLABORATION_ADAPTER,
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
