import { env } from "@/lib/env";
import { BackendEmployeesAdapter } from "./backend-adapter";
import { MockEmployeesAdapter } from "./mock-adapter";
import type { EmployeesBackendSupport } from "./support";
import type { EmployeeDraft, EmployeesAdapter } from "./types";

/**
 * The app's single entry point to employee data, and the only place that knows
 * which adapter is active. Callers (the feature hooks) never import an adapter.
 *
 * Sprint 18.2 swapped the default from the Sprint 17.6 mock to the real FastAPI
 * backend. The mock stays selectable via `NEXT_PUBLIC_EMPLOYEES_ADAPTER=mock`
 * for offline UI work; the choice is app-wide, so mock and real employees are
 * never mixed in one view.
 */
const adapter: EmployeesAdapter =
  env.NEXT_PUBLIC_EMPLOYEES_ADAPTER === "mock"
    ? new MockEmployeesAdapter()
    : new BackendEmployeesAdapter();

export const employeesService = {
  /**
   * What the active backend can do. The UI reads this to disable entry points
   * rather than offering an action that is guaranteed to fail.
   */
  support: adapter.support as Readonly<EmployeesBackendSupport>,
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

