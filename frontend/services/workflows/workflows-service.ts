import { env } from "@/lib/env";
import { BackendWorkflowsAdapter } from "./backend-adapter";
import { MockWorkflowsAdapter } from "./mock-adapter";
import type { WorkflowDraft, WorkflowsAdapter } from "./types";

/**
 * The app's single entry point to workflow data, and the only place that knows
 * which adapter is active. Callers (the feature hooks) never import an adapter.
 *
 * Sprint 18.4 swapped the default from the Sprint 17.5 mock to the real FastAPI
 * backend built in Sprint 18.3. The mock stays selectable via
 * `NEXT_PUBLIC_WORKFLOWS_ADAPTER=mock` for offline UI work; the choice is
 * app-wide, so mock and real workflows are never mixed in one view.
 */
const adapter: WorkflowsAdapter =
  env.NEXT_PUBLIC_WORKFLOWS_ADAPTER === "mock"
    ? new MockWorkflowsAdapter()
    : new BackendWorkflowsAdapter();

export const workflowsService = {
  list: () => adapter.list(),
  detail: (id: string) => adapter.detail(id),
  save: (draft: WorkflowDraft) => adapter.save(draft),
  duplicate: (id: string) => adapter.duplicate(id),
  publish: (id: string) => adapter.publish(id),
  unpublish: (id: string) => adapter.unpublish(id),
  archive: (id: string) => adapter.archive(id),
  restore: (id: string) => adapter.restore(id),
  remove: (id: string) => adapter.remove(id),
  execute: (id: string) => adapter.execute(id),
  executions: (id: string) => adapter.executions(id),
  execution: (executionId: string) => adapter.execution(executionId),
  retry: (executionId: string) => adapter.retry(executionId),
  templates: () => adapter.templates(),
  template: (id: string) => adapter.template(id),
};

export type WorkflowsService = typeof workflowsService;
