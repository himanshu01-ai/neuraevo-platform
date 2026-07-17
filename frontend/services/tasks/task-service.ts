import { MockTasksAdapter } from "./mock-adapter";
import type { ApprovalDecision, TaskCommand, TaskDraft, TasksAdapter } from "./types";

/**
 * The app's single entry point to task data. Swapping providers = swapping this
 * one adapter; callers (the feature hooks) never change. No fetch/axios/SDKs.
 */
const adapter: TasksAdapter = new MockTasksAdapter();

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
};

export type TaskService = typeof taskService;
