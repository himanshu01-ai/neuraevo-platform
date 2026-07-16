import { MockWorkflowsAdapter } from "./mock-adapter";
import type { WorkflowDraft, WorkflowsAdapter } from "./types";

/**
 * The app's single entry point to workflow data. Swapping providers = swapping
 * this one adapter; callers (the feature hooks) never change. No fetch/axios/SDKs.
 */
const adapter: WorkflowsAdapter = new MockWorkflowsAdapter();

export const workflowsService = {
  list: () => adapter.list(),
  detail: (id: string) => adapter.detail(id),
  save: (draft: WorkflowDraft) => adapter.save(draft),
  duplicate: (id: string) => adapter.duplicate(id),
  remove: (id: string) => adapter.remove(id),
  templates: () => adapter.templates(),
  template: (id: string) => adapter.template(id),
};

export type WorkflowsService = typeof workflowsService;
