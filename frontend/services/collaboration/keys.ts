/**
 * Query keys for the collaboration resource. Hierarchical so a mutation can
 * invalidate one notification (`collaborationKeys.notification(id)`) or a whole
 * feed. Shapes follow the central query-key convention (docs/09), so this table
 * lifts into that factory unchanged.
 */
export const collaborationKeys = {
  all: ["collaboration"] as const,
  notifications: ["collaboration", "notifications"] as const,
  notification: (id: string) => ["collaboration", "notification", id] as const,
  activity: ["collaboration", "activity"] as const,
  mentions: ["collaboration", "mentions"] as const,
  teamActivity: ["collaboration", "team-activity"] as const,
  approvals: ["collaboration", "approvals"] as const,
  counts: ["collaboration", "counts"] as const,
} as const;
