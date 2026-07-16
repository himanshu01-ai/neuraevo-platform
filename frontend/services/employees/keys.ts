/**
 * Query keys for the employees resource. Hierarchical so a mutation can
 * invalidate one employee (`employeeKeys.detail(id)`) or the whole list
 * (`employeeKeys.lists`).
 *
 * Scoped to this resource for now; the shapes follow the convention of the
 * central `services/query-keys.ts` factory described in docs/09, so this table
 * lifts into it unchanged when that gets built.
 */
export const employeeKeys = {
  all: ["employees"] as const,
  lists: ["employees", "list"] as const,
  detail: (id: string) => ["employees", "detail", id] as const,
  activity: (id: string) => ["employees", "activity", id] as const,
  capabilities: (id: string) => ["employees", "capabilities", id] as const,
  templates: ["employees", "templates"] as const,
  template: (id: string) => ["employees", "template", id] as const,
} as const;
