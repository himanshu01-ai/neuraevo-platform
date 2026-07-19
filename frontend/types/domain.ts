/**
 * NeuraEvo — Shared Domain Vocabulary (frontend view of the frozen backend).
 *
 * FOUNDATION ONLY. These are the enums and shapes the UI reasons about
 * (status badges, workflow nodes, capability icons). They mirror the backend
 * contracts in `backend/app/services/ai_employee/*` and MUST NOT drift.
 *
 * No business logic, no fetching — pure types + literal maps. Feature sprints
 * extend these; they never redefine the status vocabulary.
 */

/** Lifecycle status shared by tasks, sessions, and workflows (backend UPPERCASE). */
export const LIFECYCLE_STATUS = [
  "PENDING",
  "QUEUED",
  "RUNNING",
  "PAUSED",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
] as const;
export type LifecycleStatus = (typeof LIFECYCLE_STATUS)[number];

/** Human-approval decision (backend ApprovalDecisionStatus). */
export const APPROVAL_STATUS = ["PENDING", "APPROVED", "REJECTED"] as const;
export type ApprovalStatus = (typeof APPROVAL_STATUS)[number];

/** Per-node execution status in a workflow graph (backend WorkflowProgressStatus). */
export const NODE_STATUS = [
  "PENDING",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "SKIPPED",
] as const;
export type NodeStatus = (typeof NODE_STATUS)[number];

/**
 * Execution readiness of a workflow *run* — how ready its structure is to
 * proceed, not how a run is going (backend
 * planning.execution_workflow_models.WorkflowStatus). A run's progress is
 * `LifecycleStatus`; the two are different facets.
 *
 * This is separate from `WorkflowLifecycle` below: readiness describes a run,
 * lifecycle describes authoring. A workflow is authored (draft → published →
 * archived) long before any run is evaluated for readiness.
 */
export const WORKFLOW_STATUS = ["PLANNED", "READY", "WAITING", "BLOCKED"] as const;
export type WorkflowStatus = (typeof WORKFLOW_STATUS)[number];

/**
 * Authoring lifecycle of a workflow *definition* (backend
 * `app.utils.constants.WorkflowStatus`, Sprint 18.3). How far along its author
 * is — not how ready a run is, and not how a run is going.
 *
 * Kept as UPPERCASE frontend vocabulary rather than the backend's lowercase
 * values; the adapter maps between them, so no component sees a backend enum.
 * Deliberately distinct from `WorkflowStatus`: an authored workflow has a
 * lifecycle, and only gains a run status once the platform evaluates it.
 */
export const WORKFLOW_LIFECYCLE = ["DRAFT", "PUBLISHED", "ARCHIVED"] as const;
export type WorkflowLifecycle = (typeof WORKFLOW_LIFECYCLE)[number];

/** How a workflow's steps would be ordered (backend ExecutionMode). */
export const EXECUTION_MODE = ["SEQUENTIAL", "PARALLEL", "HYBRID"] as const;
export type ExecutionMode = (typeof EXECUTION_MODE)[number];

/** System health rollup (backend HealthState). */
export type HealthState = "HEALTHY" | "DEGRADED" | "UNHEALTHY" | "UNKNOWN";

/** Priority scale (tasks, notifications, recommendations). */
export type Priority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

/**
 * The executable capabilities surfaced as first-class screens. Order here is
 * the canonical order used by navigation and the capability grid.
 */
export const CAPABILITIES = [
  "browser",
  "python",
  "files",
  "email",
  "calendar",
  "github",
] as const;
export type Capability = (typeof CAPABILITIES)[number];

/**
 * Design tone a status maps to. The StatusBadge and any status-colored surface
 * resolve a status → tone through the maps below, never with inline conditionals.
 */
export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

export const LIFECYCLE_TONE: Record<LifecycleStatus, StatusTone> = {
  PENDING: "neutral",
  QUEUED: "info",
  RUNNING: "info",
  PAUSED: "warning",
  COMPLETED: "success",
  FAILED: "danger",
  CANCELLED: "neutral",
};

export const APPROVAL_TONE: Record<ApprovalStatus, StatusTone> = {
  PENDING: "warning",
  APPROVED: "success",
  REJECTED: "danger",
};

export const NODE_TONE: Record<NodeStatus, StatusTone> = {
  PENDING: "neutral",
  RUNNING: "info",
  COMPLETED: "success",
  FAILED: "danger",
  SKIPPED: "neutral",
};

export const HEALTH_TONE: Record<HealthState, StatusTone> = {
  HEALTHY: "success",
  DEGRADED: "warning",
  UNHEALTHY: "danger",
  UNKNOWN: "neutral",
};

export const WORKFLOW_TONE: Record<WorkflowStatus, StatusTone> = {
  PLANNED: "neutral",
  READY: "success",
  WAITING: "warning",
  BLOCKED: "danger",
};

/**
 * Lifecycle → tone. `ARCHIVED` is `warning`, not `danger`: archiving is a
 * reversible retirement, not an error, so it must not read in the destructive
 * colour the old `archived → BLOCKED` mapping gave it.
 */
export const WORKFLOW_LIFECYCLE_TONE: Record<WorkflowLifecycle, StatusTone> = {
  DRAFT: "neutral",
  PUBLISHED: "success",
  ARCHIVED: "warning",
};

/** Human-readable labels (sentence case for UI; backend stays UPPERCASE). */
export const LIFECYCLE_LABEL: Record<LifecycleStatus, string> = {
  PENDING: "Pending",
  QUEUED: "Queued",
  RUNNING: "Running",
  PAUSED: "Paused",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export const APPROVAL_LABEL: Record<ApprovalStatus, string> = {
  PENDING: "Pending",
  APPROVED: "Approved",
  REJECTED: "Rejected",
};

export const NODE_LABEL: Record<NodeStatus, string> = {
  PENDING: "Pending",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
  SKIPPED: "Skipped",
};

/**
 * Readiness wording. DEGRADED reads as "Warning" and UNHEALTHY as "Offline" —
 * the operator-facing words for those states. The backend vocabulary is
 * unchanged; only the label differs.
 */
export const HEALTH_LABEL: Record<HealthState, string> = {
  HEALTHY: "Healthy",
  DEGRADED: "Warning",
  UNHEALTHY: "Offline",
  UNKNOWN: "Unknown",
};

export const PRIORITY_LABEL: Record<Priority, string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  URGENT: "Urgent",
};

export const PRIORITY_TONE: Record<Priority, StatusTone> = {
  LOW: "neutral",
  MEDIUM: "info",
  HIGH: "warning",
  URGENT: "danger",
};

export const WORKFLOW_LABEL: Record<WorkflowStatus, string> = {
  PLANNED: "Planned",
  READY: "Ready",
  WAITING: "Waiting",
  BLOCKED: "Blocked",
};

export const WORKFLOW_LIFECYCLE_LABEL: Record<WorkflowLifecycle, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  ARCHIVED: "Archived",
};

export const EXECUTION_MODE_LABEL: Record<ExecutionMode, string> = {
  SEQUENTIAL: "Sequential",
  PARALLEL: "Parallel",
  HYBRID: "Hybrid",
};

export const CAPABILITY_LABEL: Record<Capability, string> = {
  browser: "Browser",
  python: "Python",
  files: "Files",
  email: "Email",
  calendar: "Calendar",
  github: "GitHub",
};
