import { env } from "@/lib/env";
import { BackendTasksAdapter } from "./backend-adapter";
import { MockTasksAdapter } from "./mock-adapter";
import type { ApprovalDecision, TaskCommand, TaskDraft, TasksAdapter } from "./types";

/**
 * The app's single entry point to task data, and the only place that knows
 * which adapter is active. Callers (the feature hooks) never import an adapter.
 *
 * Sprint 19 swapped the default from the Sprint 17.7 mock to the real FastAPI
 * Task Engine. The mock stays selectable via `NEXT_PUBLIC_TASKS_ADAPTER=mock`
 * for offline UI work; the choice is app-wide, so mock and real tasks are
 * never mixed in one view.
 */
const adapter: TasksAdapter =
  env.NEXT_PUBLIC_TASKS_ADAPTER === "mock"
    ? new MockTasksAdapter()
    : new BackendTasksAdapter();

export const taskService = {
  list: () => adapter.list(),
  detail: (id: string) => adapter.detail(id),
  create: (draft: TaskDraft) => adapter.create(draft),
  duplicate: (id: string) => adapter.duplicate(id),
  command: (id: string, command: TaskCommand) => adapter.command(id, command),
  assignWorkflow: (id: string, workflowId: string) => adapter.assignWorkflow(id, workflowId),
  assignEmployee: (id: string, employeeId: string) => adapter.assignEmployee(id, employeeId),
  timeline: (id: string) => adapter.timeline(id),
  artifacts: (id: string) => adapter.artifacts(id),
  approvals: (id: string) => adapter.approvals(id),
  allApprovals: () => adapter.allApprovals(),
  decide: (decision: ApprovalDecision) => adapter.decide(decision),
  queue: () => adapter.queue(),
  execute: (id: string) => adapter.execute(id),
  executions: (id: string) => adapter.executions(id),
  retryExecution: (id: string, executionId: string) => adapter.retryExecution(id, executionId),
};

export type TaskService = typeof taskService;
