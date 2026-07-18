/**
 * What the active employee backend can actually do.
 *
 * The FastAPI service currently exposes create, list and get for employees and
 * nothing else — no update, no delete, no status change, and no storage for
 * capabilities, permissions, behaviour settings or appearance. Rather than let
 * that leak into components as scattered checks, each adapter declares its
 * support here and the UI reads one flag to decide whether to offer an action
 * or disable it with an explanation.
 *
 * This exists because the backend is incomplete, not because the feature is
 * optional: every flag flips to `true` and the gating disappears once the
 * matching endpoint ships.
 */
export interface EmployeesBackendSupport {
  /** `PATCH /employees/{id}` — editing an employee that already exists. */
  update: boolean;
  /** Taking an employee out of service. */
  archive: boolean;
  /** `DELETE /employees/{id}`. */
  remove: boolean;
  /** An append-only history of what happened to an employee. */
  activity: boolean;
  /** Which capabilities an employee holds, and what the platform offers. */
  capabilities: boolean;
  /** Workflow assignments, current task and queue. */
  assignments: boolean;
  /** Persisting permission levels. */
  permissions: boolean;
  /** Persisting autonomy, tone, execution mode, priority and approval. */
  configuration: boolean;
  /** Persisting the chosen accent and glyph. */
  appearance: boolean;
}

/** Shown wherever a control is disabled because the backend can't back it. */
export const UNSUPPORTED_MESSAGE = "Not yet supported by the backend.";

/** Tooltip for an action that exists in the UI but cannot run yet. */
export const UNSUPPORTED_ACTION_HINT = "Available when supported by the backend";

