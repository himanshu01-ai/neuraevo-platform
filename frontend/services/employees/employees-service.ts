import { MockEmployeesAdapter } from "./mock-adapter";
import type { EmployeeDraft, EmployeesAdapter } from "./types";

/**
 * The app's single entry point to employee data. Swapping providers = swapping
 * this one adapter; callers (the feature hooks) never change. No fetch/axios/SDKs.
 */
const adapter: EmployeesAdapter = new MockEmployeesAdapter();

export const employeesService = {
  list: () => adapter.list(),
  detail: (id: string) => adapter.detail(id),
  save: (draft: EmployeeDraft) => adapter.save(draft),
  duplicate: (id: string) => adapter.duplicate(id),
  archive: (id: string) => adapter.archive(id),
  remove: (id: string) => adapter.remove(id),
  activity: (id: string) => adapter.activity(id),
  capabilities: (id: string) => adapter.capabilities(id),
  templates: () => adapter.templates(),
  template: (id: string) => adapter.template(id),
};

export type EmployeesService = typeof employeesService;
