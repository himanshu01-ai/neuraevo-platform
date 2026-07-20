/**
 * Query keys for the tasks resource. Hierarchical so a mutation can invalidate
 * one task (`taskKeys.detail(id)`) or the whole list (`taskKeys.lists`).
 *
 * Scoped to this resource for now; the shapes follow the convention of the
 * central `services/query-keys.ts` factory described in docs/09, so this table
 * lifts into it unchanged when that gets built.
 */
export const taskKeys = {
  all: ["tasks"] as const,
  lists: ["tasks", "list"] as const,
  detail: (id: string) => ["tasks", "detail", id] as const,
  timeline: (id: string) => ["tasks", "timeline", id] as const,
  artifacts: (id: string) => ["tasks", "artifacts", id] as const,
  approvals: (id: string) => ["tasks", "approvals", id] as const,
  allApprovals: ["tasks", "approvals", "all"] as const,
  queue: ["tasks", "queue"] as const,
  executions: (id: string) => ["tasks", "executions", id] as const,
} as const;
