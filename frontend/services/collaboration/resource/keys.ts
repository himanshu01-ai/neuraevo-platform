/**
 * Query keys for the resource-collaboration surface. Hierarchical so a mutation
 * can invalidate one resource's participants, shares, activity, or access
 * without touching another resource's cache.
 */
import type { CollaborationResourceType } from "./types";

export const resourceCollaborationKeys = {
  all: ["resource-collaboration"] as const,
  resource: (rt: CollaborationResourceType, rid: string) =>
    ["resource-collaboration", rt, rid] as const,
  access: (rt: CollaborationResourceType, rid: string) =>
    ["resource-collaboration", rt, rid, "access"] as const,
  participants: (rt: CollaborationResourceType, rid: string) =>
    ["resource-collaboration", rt, rid, "participants"] as const,
  shares: (rt: CollaborationResourceType, rid: string) =>
    ["resource-collaboration", rt, rid, "shares"] as const,
  activity: (rt: CollaborationResourceType, rid: string) =>
    ["resource-collaboration", rt, rid, "activity"] as const,
} as const;
