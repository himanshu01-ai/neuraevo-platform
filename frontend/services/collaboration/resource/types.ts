/**
 * Resource-collaboration contracts (Sprint 20E).
 *
 * The participant, share-link, and activity surface for any collaborated
 * resource — conversation, task, workflow, or memory. Unlike the notification
 * center (which has an offline mock), this surface is served entirely by the
 * Sprint 20 Collaboration Platform, so there is one backend-only service and no
 * projection: every field here maps to a real endpoint's response.
 */

export const COLLABORATION_RESOURCE_TYPES = [
  "conversation",
  "task",
  "workflow",
  "memory",
] as const;
export type CollaborationResourceType =
  (typeof COLLABORATION_RESOURCE_TYPES)[number];

export const COLLABORATION_ROLES = ["owner", "editor", "viewer"] as const;
export type CollaborationRole = (typeof COLLABORATION_ROLES)[number];

export const COLLABORATION_ROLE_LABEL: Record<CollaborationRole, string> = {
  owner: "Owner",
  editor: "Editor",
  viewer: "Viewer",
};

export type ParticipantType = "user" | "employee";

/** A collaborator on a resource. `id` is null for the synthetic owner entry. */
export interface ResourceParticipant {
  id: string | null;
  resourceType: CollaborationResourceType;
  resourceId: string;
  participantType: ParticipantType;
  role: CollaborationRole;
  isOwner: boolean;
  userId: string | null;
  employeeId: string | null;
  name: string;
  createdAt: string | null;
}

/** The authenticated user's effective role on a resource. */
export interface ResourceAccess {
  resourceType: CollaborationResourceType;
  resourceId: string;
  role: CollaborationRole;
  isOwner: boolean;
}

/** A share link as the owner's management view shows it (never the token). */
export interface ShareLink {
  id: string;
  resourceType: CollaborationResourceType;
  resourceId: string;
  role: CollaborationRole;
  createdByUserId: string;
  isActive: boolean;
  expiresAt: string | null;
  revokedAt: string | null;
  createdAt: string;
}

/** The one-time creation result — the only place the raw token appears. */
export interface CreatedShareLink extends ShareLink {
  token: string;
  path: string;
}

/** One timeline event on a resource. */
export interface ResourceActivity {
  id: string;
  kind: string;
  actorType: "user" | "employee" | "system";
  actorId: string | null;
  actorName: string;
  summary: string;
  isOwn: boolean;
  createdAt: string;
}

export interface AddParticipantInput {
  participantType: ParticipantType;
  userId?: string;
  employeeId?: string;
  role: CollaborationRole;
}

export interface CreateShareInput {
  role: CollaborationRole;
  expiresInDays?: number | null;
}

export type ResourceCollaborationCode =
  | "not_found"
  | "forbidden"
  | "conflict"
  | "invalid"
  | "unavailable"
  | "unknown";

export class ResourceCollaborationError extends Error {
  code: ResourceCollaborationCode;
  constructor(code: ResourceCollaborationCode, message: string) {
    super(message);
    this.name = "ResourceCollaborationError";
    this.code = code;
  }
}
