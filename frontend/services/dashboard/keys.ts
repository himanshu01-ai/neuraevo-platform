/**
 * Query keys for the dashboard resource. Hierarchical so invalidation can target
 * one widget (`dashboardKeys.health`) or the whole surface (`dashboardKeys.all`).
 *
 * Scoped to this resource for now. When the central `services/query-keys.ts`
 * factory described in docs/09 is built, this table lifts into it unchanged —
 * the key shapes already follow its convention.
 */
export const dashboardKeys = {
  all: ["dashboard"] as const,
  overview: ["dashboard", "overview"] as const,
  tasks: ["dashboard", "tasks"] as const,
  workflows: ["dashboard", "workflows"] as const,
  employees: ["dashboard", "employees"] as const,
  approvals: ["dashboard", "approvals"] as const,
  memory: ["dashboard", "memory"] as const,
  notifications: ["dashboard", "notifications"] as const,
  health: ["dashboard", "health"] as const,
  signals: ["dashboard", "signals"] as const,
} as const;
