import { z } from "zod";
import { ApiError, request } from "../http";
import { toWorkflowRunPage, workflowRunPageSchema } from "../workflows/mapping";
import type { WorkflowRunPage } from "../workflows/types";
import {
  taskListSchema,
  taskResponseSchema,
  toCreatePayload,
  toTaskDetail,
  toTaskSummary,
} from "./mapping";
import {
  TaskError,
  type Approval,
  type ApprovalDecision,
  type Artifact,
  type ArtifactKind,
  type QueueSnapshot,
  type TaskCommand,
  type TaskDetail,
  type TaskDraft,
  type TaskSummary,
  type TasksAdapter,
  type TimelineEvent,
} from "./types";

/**
 * Real task adapter, backed by the FastAPI service. Implements the same
 * `TasksAdapter` seam as the mock, so no caller changes.
 *
 * Sprint 19 built the backend Task Engine; this is the integration:
 *
 *   GET    /tasks                                     list
 *   POST   /tasks                                     create
 *   GET    /tasks/{id}                                detail
 *   PATCH  /tasks/{id}                                update / assign / attach
 *   POST   /tasks/{id}/duplicate                      duplicate
 *   POST   /tasks/{id}/command                        queue/pause/resume/cancel/retry
 *   POST   /tasks/{id}/execute                        launch the attached workflow
 *   GET    /tasks/{id}/executions                     the runs it launched
 *   POST   /tasks/{id}/executions/{eid}/retry         repeat one of them
 *   GET    /workflow-executions/{eid}                 one run in full (reused)
 *
 * Ownership and auth are the backend's; `services/http.ts` attaches and
 * refreshes the token on its own. Command legality is the backend's too — the
 * same table the toolbar disables buttons from, enforced where it can't be
 * stale.
 *
 * Approvals deliberately answer empty: the human-approval engine is not yet
 * integrated with the platform, and an empty inbox is the truth. The screens
 * already render honest empty states for it.
 */

function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new TaskError("unknown", "The server returned an unexpected response.");
  }
  return result.data;
}

/** Map a transport-level `ApiError` onto the task domain's vocabulary. */
function toTaskError(error: unknown, fallback: string): TaskError {
  if (error instanceof TaskError) return error;

  if (error instanceof ApiError) {
    if (error.isNetworkError) return new TaskError("unavailable", error.message);
    // 403 means the task belongs to someone else. Saying "not found" keeps one
    // message for both, which is also what the directory should show.
    if (error.status === 404 || error.status === 403) {
      return new TaskError("not_found", "That task doesn't exist.");
    }
    // 409 is the state machine refusing — a command or launch the task's
    // current state forbids. The backend's wording is written for a person.
    if (error.status === 409) return new TaskError("not_permitted", error.message);
    // 422 is a rejected draft or reference — but a `detail` that is a *list*
    // is FastAPI rejecting the request's own shape, and "path.task_id:
    // invalid uuid" tells a user nothing they can act on.
    if (error.status === 422) {
      return Array.isArray(error.details)
        ? new TaskError("unknown", fallback)
        : new TaskError("invalid_draft", error.message);
    }
    if (error.status >= 500) return new TaskError("unavailable", error.message);
    return new TaskError("unknown", error.message);
  }

  return new TaskError("unknown", fallback);
}

/** Artifact descriptors ride on execution steps; this reads them defensively. */
const executionArtifactStepsSchema = z.object({
  steps: z
    .array(
      z.object({
        step_id: z.string(),
        capability: z.string(),
        artifacts: z.array(z.record(z.unknown())).nullable().optional(),
      })
    )
    .nullable()
    .optional(),
});

const ARTIFACT_KIND_BY_TYPE: Record<string, ArtifactKind> = {
  document: "document",
  code: "code",
  file: "file",
  email: "email",
  report: "report",
  log: "log",
};

const toArtifactKind = (value: unknown): ArtifactKind =>
  typeof value === "string"
    ? (ARTIFACT_KIND_BY_TYPE[value.trim().toLowerCase()] ?? "file")
    : "file";

/** Millisecond ordinal for a timeline — higher is more recent. */
const toEventSequence = (iso: string): number => {
  const parsed = Date.parse(iso);
  return Number.isNaN(parsed) ? 0 : parsed;
};

export class BackendTasksAdapter implements TasksAdapter {
  // --- Reads -------------------------------------------------------------

  async list(): Promise<TaskSummary[]> {
    try {
      const raw = await request<unknown>("/tasks");
      return parseOrThrow(taskListSchema, raw)
        .map(toTaskSummary)
        // Newest first, matching the directory's existing ordering.
        .sort((a, b) => b.sequence - a.sequence);
    } catch (error) {
      throw toTaskError(error, "Unable to load tasks.");
    }
  }

  async detail(id: string): Promise<TaskDetail> {
    try {
      const raw = await request<unknown>(`/tasks/${encodeURIComponent(id)}`);
      return toTaskDetail(parseOrThrow(taskResponseSchema, raw));
    } catch (error) {
      throw toTaskError(error, "Unable to load that task.");
    }
  }

  // --- Writes ------------------------------------------------------------

  async create(draft: TaskDraft): Promise<TaskDetail> {
    if (!draft.name.trim()) {
      throw new TaskError("invalid_draft", "A task needs a name.");
    }
    try {
      const raw = await request<unknown>("/tasks", {
        method: "POST",
        body: toCreatePayload(draft),
      });
      return toTaskDetail(parseOrThrow(taskResponseSchema, raw));
    } catch (error) {
      throw toTaskError(error, "That couldn't be saved.");
    }
  }

  async duplicate(id: string): Promise<TaskDetail> {
    try {
      const raw = await request<unknown>(`/tasks/${encodeURIComponent(id)}/duplicate`, {
        method: "POST",
        body: {},
      });
      return toTaskDetail(parseOrThrow(taskResponseSchema, raw));
    } catch (error) {
      throw toTaskError(error, "That couldn't be duplicated.");
    }
  }

  /**
   * Ask the platform for a state change. Legality is the backend's call — it
   * owns the same command table the toolbar reads, so a stale button gets a
   * clear refusal rather than a silent lie.
   */
  async command(id: string, command: TaskCommand): Promise<TaskDetail> {
    try {
      const raw = await request<unknown>(`/tasks/${encodeURIComponent(id)}/command`, {
        method: "POST",
        body: { command },
      });
      return toTaskDetail(parseOrThrow(taskResponseSchema, raw));
    } catch (error) {
      throw toTaskError(error, "That couldn't be done.");
    }
  }

  /** An empty id clears the reference; anything else assigns or reassigns. */
  async assignWorkflow(id: string, workflowId: string): Promise<TaskDetail> {
    return this.patch(id, { workflow_id: workflowId || null }, "That workflow couldn't be attached.");
  }

  async assignEmployee(id: string, employeeId: string): Promise<TaskDetail> {
    return this.patch(id, { employee_id: employeeId || null }, "That employee couldn't be assigned.");
  }

  private async patch(
    id: string,
    body: Record<string, unknown>,
    fallback: string
  ): Promise<TaskDetail> {
    try {
      const raw = await request<unknown>(`/tasks/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body,
      });
      return toTaskDetail(parseOrThrow(taskResponseSchema, raw));
    } catch (error) {
      throw toTaskError(error, fallback);
    }
  }

  // --- Execution (the Workflow-platform bridge) ---------------------------

  /**
   * Launch the attached workflow. The platform owns every rule about running —
   * whether the task may launch, whether the workflow is published, how its
   * graph becomes steps. The response is the run's result, but the screens
   * render the *task*, so the task is re-read as the run left it.
   */
  async execute(id: string): Promise<TaskDetail> {
    try {
      await request<unknown>(`/tasks/${encodeURIComponent(id)}/execute`, {
        method: "POST",
        body: {},
      });
      return await this.detail(id);
    } catch (error) {
      throw toTaskError(error, "That task couldn't be run.");
    }
  }

  /** The runs this task launched, newest first. Summaries only. */
  async executions(id: string): Promise<WorkflowRunPage> {
    try {
      const raw = await request<unknown>(`/tasks/${encodeURIComponent(id)}/executions`);
      return toWorkflowRunPage(parseOrThrow(workflowRunPageSchema, raw));
    } catch (error) {
      throw toTaskError(error, "That task's run history couldn't be loaded.");
    }
  }

  /** Repeat one of this task's runs. History is immutable; this adds a run. */
  async retryExecution(id: string, executionId: string): Promise<TaskDetail> {
    try {
      await request<unknown>(
        `/tasks/${encodeURIComponent(id)}/executions/${encodeURIComponent(executionId)}/retry`,
        { method: "POST", body: {} }
      );
      return await this.detail(id);
    } catch (error) {
      throw toTaskError(error, "That run couldn't be repeated.");
    }
  }

  // --- Derived reads ------------------------------------------------------
  //
  // The backend records facts (the task, its runs); these views are assembled
  // from those facts here, in the adapter, so no component ever derives them.

  /**
   * The task's story, newest first: its creation, then each run's start and
   * outcome — all read from records, none invented.
   */
  async timeline(id: string): Promise<TimelineEvent[]> {
    try {
      const [task, runs] = await Promise.all([
        request<unknown>(`/tasks/${encodeURIComponent(id)}`),
        request<unknown>(`/tasks/${encodeURIComponent(id)}/executions`),
      ]);
      const parsed = parseOrThrow(taskResponseSchema, task);
      const page = toWorkflowRunPage(parseOrThrow(workflowRunPageSchema, runs));

      const events: TimelineEvent[] = [
        {
          id: `tl_${parsed.id}_created`,
          kind: "TASK_CREATED",
          summary: `${parsed.business_id} created`,
          nodeId: null,
          sequence: toEventSequence(parsed.created_at),
        },
      ];

      for (const run of page.items) {
        events.push({
          id: `tl_${run.id}_started`,
          kind: "WORKFLOW_STARTED",
          summary: run.trigger === "retry" ? "Run started (retry)" : "Run started",
          nodeId: "workflow",
          sequence: toEventSequence(run.startedAt),
        });
        events.push({
          id: `tl_${run.id}_finished`,
          kind: "TASK_COMPLETED",
          summary:
            run.status === "COMPLETED"
              ? `Run completed — ${run.completedStepCount} of ${run.totalStepCount} steps`
              : (run.error ?? `Run failed — ${run.completedStepCount} of ${run.totalStepCount} steps`),
          nodeId: "workflow",
          // A run can start and finish in the same millisecond; +1 keeps the
          // outcome after its start without inventing a time.
          sequence: toEventSequence(run.finishedAt) + 1,
        });
      }

      return events.sort((a, b) => b.sequence - a.sequence);
    } catch (error) {
      throw toTaskError(error, "That task's timeline couldn't be loaded.");
    }
  }

  /**
   * What the task's runs produced: the artifact descriptors history kept on
   * the latest run's steps. Descriptors only — contents stay wherever the
   * capability put them, exactly as history stores it.
   */
  async artifacts(id: string): Promise<Artifact[]> {
    try {
      const raw = await request<unknown>(`/tasks/${encodeURIComponent(id)}/executions`);
      const page = toWorkflowRunPage(parseOrThrow(workflowRunPageSchema, raw));
      const latest = page.items[0];
      if (!latest) return [];

      const detail = await request<unknown>(
        `/workflow-executions/${encodeURIComponent(latest.id)}`
      );
      const { steps } = parseOrThrow(executionArtifactStepsSchema, detail);

      const artifacts: Artifact[] = [];
      for (const step of steps ?? []) {
        for (const [index, descriptor] of (step.artifacts ?? []).entries()) {
          const name = descriptor.name;
          artifacts.push({
            id:
              typeof descriptor.reference_id === "string"
                ? descriptor.reference_id
                : `${step.step_id}_artifact_${index}`,
            kind: toArtifactKind(descriptor.artifact_type),
            name: typeof name === "string" && name ? name : "Artifact",
            description: `Produced by ${step.capability}`,
            size: "—",
            preview: null,
            sequence: artifacts.length + 1,
          });
        }
      }
      return artifacts.reverse();
    } catch (error) {
      throw toTaskError(error, "That task's artifacts couldn't be loaded.");
    }
  }

  /**
   * The waiting line, derived from the one fact the backend keeps: which tasks
   * are QUEUED. Ordered oldest first — the platform would pick up the task
   * that has waited longest.
   */
  async queue(): Promise<QueueSnapshot> {
    const tasks = await this.list();
    const entries = tasks
      .filter((t) => t.state === "QUEUED")
      .sort((a, b) => a.sequence - b.sequence)
      .map((task, index) => ({
        taskId: task.id,
        taskName: task.name,
        businessId: task.businessId,
        position: index + 1,
        priority: task.priority,
        executionMode: task.executionMode,
        employeeName: task.assignee?.employeeName ?? "Unassigned",
        estimatedOrder: index === 0 ? "Next up" : `${index} ahead of it`,
      }));
    return { entries, waitingCount: entries.length };
  }

  // --- Approvals (not yet platform-backed) --------------------------------

  async approvals(): Promise<Approval[]> {
    return [];
  }

  async allApprovals(): Promise<Approval[]> {
    return [];
  }

  async decide(_decision: ApprovalDecision): Promise<Approval> {
    throw new TaskError(
      "unavailable",
      "Approvals aren't connected to the platform yet."
    );
  }
}
