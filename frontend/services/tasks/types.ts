/**
 * Task domain contracts — provider-independent. The tasks feature depends only
 * on these types and the `TasksAdapter` interface, never on a concrete provider.
 * Sprint 17.7 ships a deterministic mock adapter; a real backend adapter can be
 * dropped in later with zero changes to callers.
 *
 * Where a vocabulary mirrors the frozen backend it is imported from
 * `types/domain.ts` and never redefined here. Two vocabularies below have no
 * single backend enum to mirror and so are owned by this layer rather than
 * `types/domain.ts` (which mirrors backend contracts only) — the same call
 * `services/workflows/types.ts` makes for `NODE_KINDS` and
 * `services/employees/types.ts` makes for `EMPLOYEE_STATUS`. Each says why in
 * place.
 *
 * Nothing in this layer executes anything. It describes a task and reports what
 * the platform would say about it; the backend is what runs one.
 */

import type { CanvasPosition } from "@/services/workflows";
import {
  LIFECYCLE_LABEL,
  LIFECYCLE_TONE,
  type ApprovalStatus,
  type HealthState,
  type LifecycleStatus,
  type NodeStatus,
  type Priority,
  type StatusTone,
} from "@/types/domain";

/**
 * Deterministic ordinal standing in for recency, mirroring the backend's
 * `generated_sequence`. Higher is more recent. No clock times.
 */
export type Sequence = number;

// =====================================================================
// Task state
// =====================================================================

/**
 * Where a task stands.
 *
 * Seven of these are the backend's own `LifecycleStatus` (`types/domain.ts`) and
 * keep its spelling exactly. Three have no lifecycle counterpart — the backend's
 * `WorkflowLifecycleStatus` has no PLANNING, WAITING_APPROVAL or BLOCKED — so
 * this list cannot live in `types/domain.ts` without claiming a contract that
 * isn't there. Each of the three is still named in the platform's own words:
 * PLANNING after the Planning Engine, WAITING_APPROVAL after the
 * `APPROVAL_REQUIRED` notification event, BLOCKED after `WorkflowStatus.BLOCKED`.
 *
 * Ordered as a task moves, not alphabetically — filters and legends read this
 * order.
 */
export const TASK_STATES = [
  "PENDING",
  "QUEUED",
  "PLANNING",
  "RUNNING",
  "WAITING_APPROVAL",
  "PAUSED",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "BLOCKED",
] as const;
export type TaskState = (typeof TASK_STATES)[number];

/**
 * A backend lifecycle status *is* a task state of the same name.
 *
 * This is the seam Sprint 17.8 reports through, and it only compiles while every
 * `LifecycleStatus` remains a `TaskState` — so if the backend vocabulary ever
 * grows, the build says so here rather than a badge silently rendering blank.
 */
export const taskStateFromLifecycle = (status: LifecycleStatus): TaskState => status;

/**
 * State → tone. Colour resolves through the one `StatusTone` scale, so a task
 * reads in the same five colours as every other status in the app. The seven
 * shared states take the backend's own tone mapping rather than restating it.
 */
export const TASK_STATE_TONE: Record<TaskState, StatusTone> = {
  ...LIFECYCLE_TONE,
  // Active work, like RUNNING.
  PLANNING: "info",
  // Stopped on a human, like PAUSED.
  WAITING_APPROVAL: "warning",
  // Can't proceed — the tone `WORKFLOW_TONE.BLOCKED` already uses.
  BLOCKED: "danger",
};

export const TASK_STATE_LABEL: Record<TaskState, string> = {
  ...LIFECYCLE_LABEL,
  PLANNING: "Planning",
  WAITING_APPROVAL: "Waiting approval",
  BLOCKED: "Blocked",
};

/** States a task will not move on from on its own. */
export const TERMINAL_TASK_STATES: readonly TaskState[] = ["COMPLETED", "FAILED", "CANCELLED"];

export const isTerminal = (state: TaskState): boolean => TERMINAL_TASK_STATES.includes(state);

/** States that breathe — the platform is doing something right now. */
export const isLive = (state: TaskState): boolean => state === "RUNNING" || state === "PLANNING";

// =====================================================================
// Execution mode
// =====================================================================

/**
 * How a task gets run.
 *
 * Deliberately *not* `ExecutionMode` from `types/domain.ts`: that mirrors the
 * backend's step-ordering (SEQUENTIAL/PARALLEL/HYBRID), which is a different
 * question from what starts a task. Both appear on this screen, so they are
 * named apart rather than overloaded.
 */
export const TASK_EXECUTION_MODES = ["AUTOMATIC", "MANUAL", "APPROVAL_REQUIRED", "SCHEDULED"] as const;
export type TaskExecutionMode = (typeof TASK_EXECUTION_MODES)[number];

export const TASK_EXECUTION_MODE_LABEL: Record<TaskExecutionMode, string> = {
  AUTOMATIC: "Automatic",
  MANUAL: "Manual",
  APPROVAL_REQUIRED: "Approval required",
  SCHEDULED: "Scheduled",
};

// =====================================================================
// Execution graph
// =====================================================================

/**
 * What a node in an execution graph stands for. This is the platform's own
 * anatomy of a run: planning decides, a workflow supplies the shape, an employee
 * carries it out, capabilities are what it reaches for, and approval, memory and
 * notification are the subsystems it touches on the way to a result.
 *
 * Frontend vocabulary — the backend describes a run as a dependency graph of
 * steps and has no node-kind enum, the same reason `NODE_KINDS` lives in
 * `services/workflows/types.ts`.
 */
export const EXECUTION_NODE_KINDS = [
  "planning",
  "workflow",
  "employee",
  "capability",
  "approval",
  "memory",
  "notification",
  "result",
] as const;
export type ExecutionNodeKind = (typeof EXECUTION_NODE_KINDS)[number];

export interface ExecutionNode {
  id: string;
  kind: ExecutionNodeKind;
  name: string;
  /** One line on what this node is doing or waiting for. */
  detail: string;
  position: CanvasPosition;
  /** Per-node status, carried from the platform. Never derived by the UI. */
  status: NodeStatus;
}

/** A directed dependency: `targetNode` depends on `sourceNode`. */
export interface ExecutionEdge {
  id: string;
  sourceNode: string;
  targetNode: string;
}

export interface ExecutionGraph {
  nodes: ExecutionNode[];
  edges: ExecutionEdge[];
}

// =====================================================================
// Monitoring
// =====================================================================

export interface ExecutionWarning {
  id: string;
  /** The node this concerns, or `null` when it's about the run as a whole. */
  nodeId: string | null;
  message: string;
}

/**
 * What the platform reports about a run in flight. Every number here is carried,
 * never recomputed: the UI does not decide how far along a task is.
 */
export interface ExecutionMonitor {
  state: TaskState;
  health: HealthState;
  /** 0–100, as the platform reports it. */
  progress: number;
  completedSteps: number;
  totalSteps: number;
  /** The node the platform says it's on, or `null` when nothing is running. */
  currentNodeId: string | null;
  /** Node ids in the order the run has visited them. */
  executionPath: string[];
  warnings: ExecutionWarning[];
  errors: ExecutionWarning[];
}

// =====================================================================
// Queue
// =====================================================================

export interface QueueEntry {
  taskId: string;
  taskName: string;
  businessId: string;
  /** 1-based place in line, as the platform ordered it. */
  position: number;
  priority: Priority;
  executionMode: TaskExecutionMode;
  employeeName: string;
  /** Plain-language note on when this would start. Never computed here. */
  estimatedOrder: string;
}

export interface QueueSnapshot {
  entries: QueueEntry[];
  /** How many are waiting, as the platform counts them. */
  waitingCount: number;
}

// =====================================================================
// Timeline
// =====================================================================

/**
 * The milestones a run passes. Named after the platform's own events where it
 * has them — `WORKFLOW_STARTED`, `WORKFLOW_COMPLETED` and `APPROVAL_REQUIRED`
 * are `WorkflowNotificationEvent` values, upper-cased to match this file.
 */
export const TIMELINE_EVENT_KINDS = [
  "TASK_CREATED",
  "QUEUED",
  "PLANNING_STARTED",
  "WORKFLOW_STARTED",
  "CAPABILITY_INVOKED",
  "APPROVAL_REQUESTED",
  "APPROVAL_COMPLETED",
  "MEMORY_UPDATED",
  "NOTIFICATION_SENT",
  "TASK_COMPLETED",
] as const;
export type TimelineEventKind = (typeof TIMELINE_EVENT_KINDS)[number];

export interface TimelineEvent {
  id: string;
  kind: TimelineEventKind;
  /** One line naming what happened. Fixture copy — nothing is inferred. */
  summary: string;
  /** The node this event came from, when it came from one. */
  nodeId: string | null;
  sequence: Sequence;
}

// =====================================================================
// Artifacts
// =====================================================================

export const ARTIFACT_KINDS = ["document", "code", "file", "email", "report", "log"] as const;
export type ArtifactKind = (typeof ARTIFACT_KINDS)[number];

export interface Artifact {
  id: string;
  kind: ArtifactKind;
  name: string;
  description: string;
  /** Human-readable size, as the platform reports it (never computed here). */
  size: string;
  /**
   * Inline preview text. `null` when the artifact has nothing to show inline —
   * the preview says so rather than rendering an empty box.
   */
  preview: string | null;
  sequence: Sequence;
}

// =====================================================================
// Approvals
// =====================================================================

export interface Approval {
  id: string;
  taskId: string;
  taskName: string;
  /** What is being asked for. */
  title: string;
  description: string;
  status: ApprovalStatus;
  requestedBy: string;
  assignedReviewer: string;
  /** The reviewer's note, once there is one. */
  comment: string | null;
  sequence: Sequence;
}

/** What the UI sends when a reviewer decides. */
export interface ApprovalDecision {
  approvalId: string;
  status: Extract<ApprovalStatus, "APPROVED" | "REJECTED">;
  comment: string;
}

// =====================================================================
// Results
// =====================================================================

export interface CapabilitySummaryEntry {
  /** Capability label as the platform names it. */
  capability: string;
  /** How many times it was reached for. Carried, never counted here. */
  invocations: number;
  outcome: string;
}

/**
 * What a finished run produced. Present only once a task reaches a terminal
 * state — a result before the end would be a guess.
 */
export interface TaskResult {
  summary: string;
  /** The platform's own report on how the run went. */
  executionReport: string;
  workflowOutcome: string;
  capabilitySummary: CapabilitySummaryEntry[];
  /** Ids into the task's artifacts. */
  generatedArtifactIds: string[];
  completionDetails: { label: string; value: string }[];
}

// =====================================================================
// Task
// =====================================================================

/** Who a task is assigned to. Identity only — the employee module owns the rest. */
export interface TaskAssignee {
  employeeId: string;
  employeeName: string;
}

/** What a task is running. Identity only — the workflow module owns the rest. */
export interface TaskWorkflowRef {
  workflowId: string;
  workflowName: string;
}

/** What the directory list and cards need. */
export interface TaskSummary {
  id: string;
  /**
   * The id a person quotes — the backend's own `task_id` on `TaskDelegation`
   * rather than the surrogate row id.
   */
  businessId: string;
  name: string;
  description: string;
  state: TaskState;
  priority: Priority;
  executionMode: TaskExecutionMode;
  workflow: TaskWorkflowRef | null;
  assignee: TaskAssignee | null;
  /** 0–100, carried from the platform. */
  progress: number;
  /** `null` when the task isn't in line. */
  queuePosition: number | null;
  sequence: Sequence;
}

/** Everything a task's own screens show. */
export interface TaskDetail extends TaskSummary {
  graph: ExecutionGraph;
  monitor: ExecutionMonitor;
  /** `null` until the task reaches a terminal state. */
  result: TaskResult | null;
}

/** What the builder hands back when creating a task. */
export interface TaskDraft {
  /** `null` for a create; an id for an edit. */
  id: string | null;
  name: string;
  description: string;
  priority: Priority;
  executionMode: TaskExecutionMode;
  workflowId: string | null;
  employeeId: string | null;
}

// =====================================================================
// Errors & the adapter seam
// =====================================================================

export type TaskErrorCode = "not_found" | "unavailable" | "invalid_draft" | "not_permitted" | "unknown";

export class TaskError extends Error {
  code: TaskErrorCode;
  constructor(code: TaskErrorCode, message: string) {
    super(message);
    this.name = "TaskError";
    this.code = code;
  }
}

/**
 * A control the toolbar offers. The adapter decides which are legal for a task
 * in its current state, so the toolbar never has to know the state machine —
 * and Sprint 17.8 can hand that judgement to the backend unchanged.
 */
export const TASK_COMMANDS = ["queue", "pause", "resume", "cancel", "retry"] as const;
export type TaskCommand = (typeof TASK_COMMANDS)[number];

/**
 * Which commands a task in each state will accept.
 *
 * One table, read by both sides: the toolbar disables what isn't offered, and
 * the adapter refuses what it isn't offered. A disabled button and a rejected
 * request can't disagree, because they're the same rule.
 *
 * A run that's WAITING_APPROVAL takes no pause or resume — the approval is what
 * moves it, and the toolbar shouldn't pretend otherwise. Terminal states accept
 * nothing but a retry, and COMPLETED not even that.
 */
export const ALLOWED_COMMANDS: Record<TaskState, readonly TaskCommand[]> = {
  PENDING: ["queue", "cancel"],
  QUEUED: ["pause", "cancel"],
  PLANNING: ["pause", "cancel"],
  RUNNING: ["pause", "cancel"],
  WAITING_APPROVAL: ["cancel"],
  PAUSED: ["resume", "cancel"],
  COMPLETED: [],
  FAILED: ["retry", "cancel"],
  CANCELLED: ["retry"],
  BLOCKED: ["cancel"],
};

export const isCommandAllowed = (state: TaskState, command: TaskCommand): boolean =>
  ALLOWED_COMMANDS[state].includes(command);

/**
 * The state a command moves a task to. Requesting is not running: `resume` puts
 * a task back to RUNNING as a claim about intent, and the platform is what
 * actually carries it out.
 */
export const COMMAND_RESULT: Record<TaskCommand, TaskState> = {
  queue: "QUEUED",
  pause: "PAUSED",
  resume: "RUNNING",
  cancel: "CANCELLED",
  retry: "QUEUED",
};

/** The single seam every task backend must implement. */
export interface TasksAdapter {
  list(): Promise<TaskSummary[]>;
  detail(id: string): Promise<TaskDetail>;
  create(draft: TaskDraft): Promise<TaskDetail>;
  duplicate(id: string): Promise<TaskDetail>;
  /** Requests a state change. The adapter refuses what the state forbids. */
  command(id: string, command: TaskCommand): Promise<TaskDetail>;
  assignWorkflow(id: string, workflowId: string): Promise<TaskDetail>;
  assignEmployee(id: string, employeeId: string): Promise<TaskDetail>;
  timeline(id: string): Promise<TimelineEvent[]>;
  artifacts(id: string): Promise<Artifact[]>;
  approvals(id: string): Promise<Approval[]>;
  /** Every approval across every task — the reviewer's inbox. */
  allApprovals(): Promise<Approval[]>;
  decide(decision: ApprovalDecision): Promise<Approval>;
  queue(): Promise<QueueSnapshot>;
}
