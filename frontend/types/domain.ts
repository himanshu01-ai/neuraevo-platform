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

export const CAPABILITY_LABEL: Record<Capability, string> = {
  browser: "Browser",
  python: "Python",
  files: "Files",
  email: "Email",
  calendar: "Calendar",
  github: "GitHub",
};
