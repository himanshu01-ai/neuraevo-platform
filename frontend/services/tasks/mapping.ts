/**
 * Backend ⇄ frontend translation for tasks (Sprint 19).
 *
 * The one place the FastAPI task vocabulary is spoken. Everything above the
 * adapter — hooks, stores, screens — sees only the Sprint 17.7 domain model,
 * so the backend's names, casing and lifecycle never leak into a component.
 *
 * Three reconciliations, each deliberate:
 *
 * 1. **Casing.** The backend stores statuses, priorities and modes lowercase
 *    (`waiting_approval`); the frontend speaks them uppercase
 *    (`WAITING_APPROVAL`). Mapped 1:1 in both directions, lossless.
 *
 * 2. **Execution history.** A task's runs are workflow runs, so their wire
 *    schemas and mapped shapes are imported from `services/workflows/mapping`
 *    rather than redefined — one vocabulary for one fact.
 *
 * 3. **Graph and monitor.** The backend describes a task's run as facts — the
 *    latest execution's status and step counts — and has no opinion about
 *    pixels. The small graph drawn from those facts (assignee → workflow →
 *    result) is assembled here and laid out by the shared deterministic
 *    layout, so the graph canvas renders backend truth without the backend
 *    inventing geometry.
 */

import { z } from "zod";
import type { HealthState, NodeStatus, Priority } from "@/types/domain";
import {
  toSequence,
  toWorkflowRunSummary,
  workflowRunSummarySchema,
} from "../workflows/mapping";
import type { WorkflowRunSummary } from "../workflows/types";
import { layoutGraph } from "./execution-graph";
import {
  TASK_EXECUTION_MODES,
  TASK_STATES,
  type ExecutionGraph,
  type ExecutionMonitor,
  type ExecutionNode,
  type TaskDetail,
  type TaskDraft,
  type TaskExecutionMode,
  type TaskResult,
  type TaskState,
  type TaskSummary,
} from "./types";

// =====================================================================
// Wire schemas
// =====================================================================

const taskWorkflowRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.string(),
});

const taskEmployeeRefSchema = z.object({
  id: z.string(),
  name: z.string(),
});

export const taskResponseSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  business_id: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  status: z.string(),
  priority: z.string(),
  execution_mode: z.string(),
  progress: z.number(),
  workflow: taskWorkflowRefSchema.nullable().optional(),
  assignee: taskEmployeeRefSchema.nullable().optional(),
  latest_execution: workflowRunSummarySchema.nullable().optional(),
  execution_count: z.number(),
  created_at: z.string(),
  updated_at: z.string().nullable().optional(),
});

export const taskListSchema = z.array(taskResponseSchema);

export type TaskResponse = z.infer<typeof taskResponseSchema>;

// =====================================================================
// Vocabularies
// =====================================================================

/**
 * Backend task status → frontend `TaskState`. A 1:1 rename, casing aside.
 * An unrecognised value reads as `PENDING` — the safe, actionable state — so a
 * newer backend status can't strand a task the UI can't act on.
 */
export function toTaskState(status: string): TaskState {
  const upper = status.trim().toUpperCase() as TaskState;
  return (TASK_STATES as readonly string[]).includes(upper) ? upper : "PENDING";
}

const PRIORITIES: readonly Priority[] = ["LOW", "MEDIUM", "HIGH", "URGENT"];

export function toTaskPriority(priority: string): Priority {
  const upper = priority.trim().toUpperCase() as Priority;
  return PRIORITIES.includes(upper) ? upper : "MEDIUM";
}

export function toTaskExecutionMode(mode: string): TaskExecutionMode {
  const upper = mode.trim().toUpperCase() as TaskExecutionMode;
  return (TASK_EXECUTION_MODES as readonly string[]).includes(upper) ? upper : "MANUAL";
}

/** Frontend vocabulary → the backend's lowercase spelling. */
const toBackendWord = (value: string): string => value.toLowerCase();

// =====================================================================
// Requests
// =====================================================================

export function toCreatePayload(draft: TaskDraft): Record<string, unknown> {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    priority: toBackendWord(draft.priority),
    execution_mode: toBackendWord(draft.executionMode),
    workflow_id: draft.workflowId,
    employee_id: draft.employeeId,
  };
}

// =====================================================================
// Responses
// =====================================================================

export function toTaskSummary(response: TaskResponse): TaskSummary {
  return {
    id: response.id,
    businessId: response.business_id,
    name: response.name,
    description: response.description ?? "",
    state: toTaskState(response.status),
    priority: toTaskPriority(response.priority),
    executionMode: toTaskExecutionMode(response.execution_mode),
    workflow: response.workflow
      ? { workflowId: response.workflow.id, workflowName: response.workflow.name }
      : null,
    assignee: response.assignee
      ? { employeeId: response.assignee.id, employeeName: response.assignee.name }
      : null,
    progress: response.progress,
    // The backend has no queue engine yet; positions are derived per snapshot
    // by the adapter's `queue()`, never carried on a task.
    queuePosition: null,
    sequence: toSequence(response.created_at),
  };
}

/**
 * The task's run drawn from backend facts.
 *
 * Three nodes at most — who carries it, what shape it runs, what came out —
 * with statuses taken from the task's state and its latest run. Nothing here
 * is estimated: a task that never ran draws its plan as PENDING, and a task
 * that ran draws what the record says happened.
 */
function toGraph(
  response: TaskResponse,
  latest: WorkflowRunSummary | null
): ExecutionGraph {
  const state = toTaskState(response.status);
  const ranStatus: NodeStatus =
    latest === null
      ? "PENDING"
      : latest.status === "COMPLETED"
        ? "COMPLETED"
        : "FAILED";
  const running = state === "RUNNING" || state === "PLANNING";

  const nodes: ExecutionNode[] = [];
  const edges: { id: string; sourceNode: string; targetNode: string }[] = [];
  const origin = { x: 0, y: 0 };

  if (response.assignee) {
    nodes.push({
      id: "assignee",
      kind: "employee",
      name: response.assignee.name,
      detail: "Carries the work",
      position: origin,
      status: latest === null ? "PENDING" : "COMPLETED",
    });
  }

  if (response.workflow) {
    nodes.push({
      id: "workflow",
      kind: "workflow",
      name: response.workflow.name,
      detail:
        latest === null
          ? "Not run yet"
          : `${latest.completedStepCount} of ${latest.totalStepCount} step${
              latest.totalStepCount === 1 ? "" : "s"
            } completed`,
      position: origin,
      status: running ? "RUNNING" : ranStatus,
    });
    if (response.assignee) {
      edges.push({ id: "assignee-workflow", sourceNode: "assignee", targetNode: "workflow" });
    }

    nodes.push({
      id: "result",
      kind: "result",
      name: "Result",
      detail:
        latest === null
          ? "Waiting for a run"
          : latest.status === "COMPLETED"
            ? "Run completed"
            : (latest.error ?? "Run failed"),
      position: origin,
      status: ranStatus === "FAILED" ? "SKIPPED" : ranStatus,
    });
    edges.push({ id: "workflow-result", sourceNode: "workflow", targetNode: "result" });
  }

  // The backend describes dependencies, not pixels; the shared deterministic
  // layout turns them into positions exactly as the mock fixtures were drawn.
  return layoutGraph({ nodes, edges });
}

function toHealth(state: TaskState, latest: WorkflowRunSummary | null): HealthState {
  if (state === "FAILED") return "UNHEALTHY";
  if (state === "BLOCKED") return "DEGRADED";
  if (state === "COMPLETED") return "HEALTHY";
  if (latest === null) return "UNKNOWN";
  return latest.status === "COMPLETED" ? "HEALTHY" : "DEGRADED";
}

function toMonitor(
  response: TaskResponse,
  latest: WorkflowRunSummary | null,
  graph: ExecutionGraph
): ExecutionMonitor {
  const state = toTaskState(response.status);
  const finished = state === "COMPLETED" || state === "FAILED";

  return {
    state,
    health: toHealth(state, latest),
    progress: response.progress,
    completedSteps: latest?.completedStepCount ?? 0,
    totalSteps: latest?.totalStepCount ?? 0,
    currentNodeId: null,
    // Where the run has been: for a finished run, the drawn path in order.
    executionPath: finished && latest !== null ? graph.nodes.map((n) => n.id) : [],
    warnings: [],
    errors:
      latest?.error && state === "FAILED"
        ? [{ id: `err_${latest.id}`, nodeId: "workflow", message: latest.error }]
        : [],
  };
}

function toResult(
  response: TaskResponse,
  latest: WorkflowRunSummary | null
): TaskResult | null {
  const state = toTaskState(response.status);
  if (latest === null || (state !== "COMPLETED" && state !== "FAILED")) return null;

  const steps = `${latest.completedStepCount} of ${latest.totalStepCount} step${
    latest.totalStepCount === 1 ? "" : "s"
  } completed`;
  const completed = latest.status === "COMPLETED";

  return {
    summary: completed
      ? `The workflow ran to completion — ${steps}.`
      : (latest.error ?? `The run stopped — ${steps}.`),
    executionReport: steps,
    workflowOutcome: completed ? "Completed" : "Failed",
    // Per-capability detail lives on the run's own record; the summary the
    // backend sends for a list doesn't carry steps, and nothing is invented.
    capabilitySummary: [],
    generatedArtifactIds: [],
    completionDetails: [
      { label: "Runs", value: String(response.execution_count) },
      { label: "Duration", value: `${latest.durationMs} ms` },
      { label: "Steps", value: steps },
      ...(latest.failedStepId ? [{ label: "Failed step", value: latest.failedStepId }] : []),
    ],
  };
}

export function toTaskDetail(response: TaskResponse): TaskDetail {
  const latest = response.latest_execution
    ? toWorkflowRunSummary(response.latest_execution)
    : null;
  const graph = toGraph(response, latest);

  return {
    ...toTaskSummary(response),
    graph,
    monitor: toMonitor(response, latest, graph),
    result: toResult(response, latest),
  };
}
