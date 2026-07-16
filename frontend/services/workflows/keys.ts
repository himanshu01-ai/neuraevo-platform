/**
 * Query keys for the workflows resource. Hierarchical so a mutation can
 * invalidate one workflow (`workflowKeys.detail(id)`) or the whole list
 * (`workflowKeys.lists`).
 *
 * Scoped to this resource for now; the shapes follow the convention of the
 * central `services/query-keys.ts` factory described in docs/09, so this table
 * lifts into it unchanged when that gets built.
 */
export const workflowKeys = {
  all: ["workflows"] as const,
  lists: ["workflows", "list"] as const,
  detail: (id: string) => ["workflows", "detail", id] as const,
  templates: ["workflows", "templates"] as const,
  template: (id: string) => ["workflows", "template", id] as const,
} as const;
