/**
 * Dashboard domain contracts — provider-independent. The dashboard depends only
 * on these types and the `DashboardAdapter` interface, never on a concrete
 * provider. Sprint 17.4 ships a deterministic mock adapter; a real backend
 * adapter can be dropped in later with zero changes to callers.
 *
 * Status vocabulary is never redefined here — it is imported from
 * `types/domain.ts`, which mirrors the frozen backend.
 */

import type {
  ApprovalStatus,
  Capability,
  HealthState,
  LifecycleStatus,
  Priority,
  StatusTone,
} from "@/types/domain";

/**
 * Deterministic ordinal standing in for recency. The backend's dashboard DTOs
 * carry a `generated_sequence` ordinal rather than a clock time, and this layer
 * does the same: lists convey order without inventing timestamps. Higher is
 * more recent.
 */
export type Sequence = number;

/**
 * Trend slot on an overview card. `direction` is `"none"` until the platform
 * exposes analytics — nothing here is computed, so no other direction is
 * produced yet. The union is the contract a real trend will arrive through.
 */
export type TrendDirection = "up" | "down" | "flat" | "none";

export interface Trend {
  direction: TrendDirection;
  label: string;
}

/** A card's qualitative state: a label plus the tone it renders in. */
export interface MetricStatus {
  label: string;
  tone: StatusTone;
}

export const OVERVIEW_METRIC_IDS = [
  "tasks",
  "workflows",
  "employees",
  "approvals",
  "memory",
  "health",
] as const;
export type OverviewMetricId = (typeof OVERVIEW_METRIC_IDS)[number];

export interface OverviewMetric {
  id: OverviewMetricId;
  /** `null` when the platform cannot report a value yet (renders as an em dash). */
  value: number | null;
  /** Short qualifier shown under the value. */
  secondary: string;
  status: MetricStatus;
  trend: Trend;
}

export interface TaskSummary {
  id: string;
  title: string;
  status: LifecycleStatus;
  capability: Capability;
  sequence: Sequence;
}

export interface WorkflowSummary {
  id: string;
  name: string;
  status: LifecycleStatus;
  /** The workflow's own node counters — carried, never recomputed by the UI. */
  completedNodes: number;
  totalNodes: number;
  sequence: Sequence;
}

export interface EmployeeSummary {
  id: string;
  name: string;
  role: string;
  status: LifecycleStatus;
  activeTasks: number;
  sequence: Sequence;
}

export interface ApprovalSummary {
  id: string;
  title: string;
  requestedBy: string;
  status: ApprovalStatus;
  priority: Priority;
  sequence: Sequence;
}

export interface NotificationSummary {
  id: string;
  title: string;
  detail: string;
  priority: Priority;
  isRead: boolean;
  sequence: Sequence;
}

export interface MemoryCategoryCount {
  /** Backend memory category label. */
  category: string;
  count: number;
}

export interface MemorySummary {
  total: number;
  categories: MemoryCategoryCount[];
}

/**
 * The subsystems the platform reports readiness for, in canonical order. These
 * are backend module names — the frozen `HealthManager.HEALTH_COMPONENTS`
 * (planning, runtime, memory, scheduler, recovery, persistence) plus the two
 * further subsystems the dashboard inspectors cover (operations, validation).
 */
export const HEALTH_SUBSYSTEMS = [
  "planning",
  "runtime",
  "memory",
  "scheduler",
  "recovery",
  "persistence",
  "operations",
  "validation",
] as const;
export type HealthSubsystem = (typeof HEALTH_SUBSYSTEMS)[number];

export interface SubsystemHealth {
  subsystem: HealthSubsystem;
  state: HealthState;
  /** Plain-text note. Never a metric. */
  detail: string;
}

export interface HealthSummary {
  state: HealthState;
  isReady: boolean;
  healthySubsystems: number;
  totalSubsystems: number;
  subsystems: SubsystemHealth[];
}

/**
 * The plain facts the suggestion rules read. Rules live in
 * `features/dashboard/models/suggestions.ts`; this layer only reports the
 * signals they match against.
 */
export interface WorkspaceSignals {
  hasCompletedOnboarding: boolean;
  workflowCount: number;
  integrationCount: number;
  teamSize: number;
  pendingApprovals: number;
  hasCustomizedEmployee: boolean;
}

export type DashboardErrorCode = "unavailable" | "unknown";

export class DashboardError extends Error {
  code: DashboardErrorCode;
  constructor(code: DashboardErrorCode, message: string) {
    super(message);
    this.name = "DashboardError";
    this.code = code;
  }
}

/** The single seam every dashboard backend must implement. */
export interface DashboardAdapter {
  overview(): Promise<OverviewMetric[]>;
  recentTasks(): Promise<TaskSummary[]>;
  recentWorkflows(): Promise<WorkflowSummary[]>;
  activeEmployees(): Promise<EmployeeSummary[]>;
  pendingApprovals(): Promise<ApprovalSummary[]>;
  memorySummary(): Promise<MemorySummary>;
  recentNotifications(): Promise<NotificationSummary[]>;
  health(): Promise<HealthSummary>;
  workspaceSignals(): Promise<WorkspaceSignals>;
}
