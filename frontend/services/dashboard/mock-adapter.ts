import {
  HEALTH_SUBSYSTEMS,
  type ApprovalSummary,
  type DashboardAdapter,
  type EmployeeSummary,
  type HealthSummary,
  type MemorySummary,
  type NotificationSummary,
  type OverviewMetric,
  type SubsystemHealth,
  type TaskSummary,
  type WorkflowSummary,
  type WorkspaceSignals,
} from "./types";

/**
 * Deterministic in-browser mock of the dashboard read model. No network, no
 * clock, no randomness — the same fixtures every render, so the UI is stable
 * across reloads and server/client hydration.
 *
 * What is fabricated and what is not:
 *  - Tasks, workflows, employees, approvals, notifications, and memory are
 *    FIXTURES standing in for user content, so every widget can be built and
 *    reviewed in its `ready` state.
 *  - Health is NOT fabricated. No backend is wired, so every subsystem reports
 *    UNKNOWN — asserting "Runtime: Healthy" would be a claim about a real
 *    deployed system. The widget renders all four states; wiring the backend
 *    flips them.
 *  - Trends are NOT computed. Every card carries a placeholder trend until the
 *    platform exposes analytics.
 *
 * Ordering uses `sequence` ordinals (mirroring the backend's
 * `generated_sequence`) rather than invented timestamps.
 */

const LATENCY_MS = 400;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

const TASKS: readonly TaskSummary[] = [
  { id: "tsk_04", title: "Summarize the Q3 revenue export", status: "RUNNING", capability: "python", sequence: 4 },
  { id: "tsk_03", title: "Draft follow-up emails for open leads", status: "PAUSED", capability: "email", sequence: 3 },
  { id: "tsk_02", title: "Collect competitor pricing pages", status: "COMPLETED", capability: "browser", sequence: 2 },
  { id: "tsk_01", title: "File the vendor invoices", status: "QUEUED", capability: "files", sequence: 1 },
];

const WORKFLOWS: readonly WorkflowSummary[] = [
  { id: "wfl_03", name: "Weekly revenue report", status: "RUNNING", completedNodes: 3, totalNodes: 5, sequence: 3 },
  { id: "wfl_02", name: "Inbox triage", status: "COMPLETED", completedNodes: 4, totalNodes: 4, sequence: 2 },
  { id: "wfl_01", name: "Release notes digest", status: "FAILED", completedNodes: 1, totalNodes: 6, sequence: 1 },
];

const EMPLOYEES: readonly EmployeeSummary[] = [
  { id: "emp_03", name: "Ada", role: "Data analyst", status: "RUNNING", activeTasks: 2, sequence: 3 },
  { id: "emp_02", name: "Iris", role: "Inbox manager", status: "PENDING", activeTasks: 0, sequence: 2 },
  { id: "emp_01", name: "Vale", role: "Research assistant", status: "PAUSED", activeTasks: 1, sequence: 1 },
];

const APPROVALS: readonly ApprovalSummary[] = [
  { id: "apr_02", title: "Send the Q3 summary to finance@", requestedBy: "Ada", status: "PENDING", priority: "HIGH", sequence: 2 },
  { id: "apr_01", title: "Grant calendar write access", requestedBy: "Iris", status: "PENDING", priority: "MEDIUM", sequence: 1 },
];

const NOTIFICATIONS: readonly NotificationSummary[] = [
  {
    id: "ntf_03",
    title: "Approval needed",
    detail: "Ada is waiting to send the Q3 summary.",
    priority: "HIGH",
    isRead: false,
    sequence: 3,
  },
  {
    id: "ntf_02",
    title: "Workflow failed",
    detail: "Release notes digest stopped at step 2.",
    priority: "URGENT",
    isRead: false,
    sequence: 2,
  },
  {
    id: "ntf_01",
    title: "Task completed",
    detail: "Competitor pricing pages were collected.",
    priority: "LOW",
    isRead: true,
    sequence: 1,
  },
];

const MEMORY: MemorySummary = {
  total: 128,
  categories: [
    { category: "Preferences", count: 46 },
    { category: "People", count: 38 },
    { category: "Projects", count: 29 },
    { category: "Facts", count: 15 },
  ],
};

/**
 * Every subsystem is UNKNOWN: nothing is wired, so nothing is known. This is the
 * one honest state for platform telemetry without a backend.
 */
const HEALTH_SUBSYSTEM_STATES: readonly SubsystemHealth[] = HEALTH_SUBSYSTEMS.map((subsystem) => ({
  subsystem,
  state: "UNKNOWN" as const,
  detail: "Awaiting platform telemetry.",
}));

const HEALTH: HealthSummary = {
  state: "UNKNOWN",
  isReady: false,
  healthySubsystems: 0,
  totalSubsystems: HEALTH_SUBSYSTEMS.length,
  subsystems: [...HEALTH_SUBSYSTEM_STATES],
};

const SIGNALS: WorkspaceSignals = {
  hasCompletedOnboarding: true,
  workflowCount: WORKFLOWS.length,
  integrationCount: 0,
  teamSize: 1,
  pendingApprovals: APPROVALS.length,
  hasCustomizedEmployee: false,
};

/** Counts are carried, not derived in the UI — a widget never computes a total. */
const OVERVIEW: readonly OverviewMetric[] = [
  {
    id: "tasks",
    value: TASKS.length,
    secondary: "1 running · 1 queued",
    status: { label: "Active", tone: "info" },
    trend: { direction: "none", label: "No trend yet" },
  },
  {
    id: "workflows",
    value: WORKFLOWS.length,
    secondary: "1 needs attention",
    status: { label: "Attention", tone: "warning" },
    trend: { direction: "none", label: "No trend yet" },
  },
  {
    id: "employees",
    value: EMPLOYEES.length,
    secondary: "1 working now",
    status: { label: "Ready", tone: "success" },
    trend: { direction: "none", label: "No trend yet" },
  },
  {
    id: "approvals",
    value: APPROVALS.length,
    secondary: "Waiting on you",
    status: { label: "Pending", tone: "warning" },
    trend: { direction: "none", label: "No trend yet" },
  },
  {
    id: "memory",
    value: MEMORY.total,
    secondary: "Across 4 categories",
    status: { label: "Stored", tone: "neutral" },
    trend: { direction: "none", label: "No trend yet" },
  },
  {
    id: "health",
    value: null,
    secondary: `0 of ${HEALTH_SUBSYSTEMS.length} subsystems reporting`,
    status: { label: "Unknown", tone: "neutral" },
    trend: { direction: "none", label: "No trend yet" },
  },
];

/** Hand back copies so a consumer can never mutate the fixtures. */
const clone = <T,>(rows: readonly T[]): T[] => rows.map((row) => ({ ...row }));

export class MockDashboardAdapter implements DashboardAdapter {
  async overview(): Promise<OverviewMetric[]> {
    await delay();
    return clone(OVERVIEW);
  }

  async recentTasks(): Promise<TaskSummary[]> {
    await delay();
    return clone(TASKS);
  }

  async recentWorkflows(): Promise<WorkflowSummary[]> {
    await delay();
    return clone(WORKFLOWS);
  }

  async activeEmployees(): Promise<EmployeeSummary[]> {
    await delay();
    return clone(EMPLOYEES);
  }

  async pendingApprovals(): Promise<ApprovalSummary[]> {
    await delay();
    return clone(APPROVALS);
  }

  async memorySummary(): Promise<MemorySummary> {
    await delay();
    return { total: MEMORY.total, categories: clone(MEMORY.categories) };
  }

  async recentNotifications(): Promise<NotificationSummary[]> {
    await delay();
    return clone(NOTIFICATIONS);
  }

  async health(): Promise<HealthSummary> {
    await delay();
    return { ...HEALTH, subsystems: clone(HEALTH.subsystems) };
  }

  async workspaceSignals(): Promise<WorkspaceSignals> {
    await delay();
    return { ...SIGNALS };
  }
}
