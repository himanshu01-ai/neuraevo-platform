/**
 * The resource-collaboration service (Sprint 20E) — participants, share links,
 * and the activity timeline for any collaborated resource, backed by the
 * FastAPI Collaboration Platform:
 *
 *   GET    /collaboration/{rt}/{rid}/access
 *   GET    /collaboration/{rt}/{rid}/participants
 *   POST   /collaboration/{rt}/{rid}/participants
 *   PATCH  /collaboration/{rt}/{rid}/participants/{id}
 *   DELETE /collaboration/{rt}/{rid}/participants/{id}
 *   GET    /collaboration/{rt}/{rid}/shares
 *   POST   /collaboration/{rt}/{rid}/shares
 *   DELETE /collaboration/{rt}/{rid}/shares/{id}
 *   POST   /collaboration/shares/redeem
 *   GET    /collaboration/{rt}/{rid}/activity
 *
 * Ownership, permissions, and every access decision are the backend's — this
 * layer validates response shapes, maps snake_case to the app's vocabulary, and
 * translates transport errors. No component ever sees a raw DTO.
 */

import { z } from "zod";
import { ApiError, request } from "../../http";
import {
  ResourceCollaborationError,
  type AddParticipantInput,
  type CollaborationResourceType,
  type CollaborationRole,
  type CreateShareInput,
  type CreatedShareLink,
  type ResourceAccess,
  type ResourceActivity,
  type ResourceParticipant,
  type ShareLink,
} from "./types";

// --- Backend DTO schemas -------------------------------------------------

const roleSchema = z.enum(["owner", "editor", "viewer"]);
const resourceTypeSchema = z.enum(["conversation", "task", "workflow", "memory"]);

const participantSchema = z.object({
  id: z.string().nullable(),
  resource_type: resourceTypeSchema,
  resource_id: z.string(),
  participant_type: z.enum(["user", "employee"]),
  role: roleSchema,
  is_owner: z.boolean(),
  user_id: z.string().nullable(),
  employee_id: z.string().nullable(),
  name: z.string(),
  created_at: z.string().nullable(),
});

const accessSchema = z.object({
  resource_type: resourceTypeSchema,
  resource_id: z.string(),
  role: roleSchema,
  is_owner: z.boolean(),
});

const shareSchema = z.object({
  id: z.string(),
  resource_type: resourceTypeSchema,
  resource_id: z.string(),
  role: roleSchema,
  created_by_user_id: z.string(),
  is_active: z.boolean(),
  expires_at: z.string().nullable(),
  revoked_at: z.string().nullable(),
  created_at: z.string(),
});

const createdShareSchema = shareSchema.extend({
  token: z.string(),
  path: z.string(),
});

const activitySchema = z.object({
  id: z.string(),
  kind: z.string(),
  actor_type: z.enum(["user", "employee", "system"]),
  actor_id: z.string().nullable(),
  actor_name: z.string(),
  summary: z.string(),
  is_own: z.boolean(),
  created_at: z.string(),
});

// --- Mappers -------------------------------------------------------------

function toParticipant(
  dto: z.infer<typeof participantSchema>
): ResourceParticipant {
  return {
    id: dto.id,
    resourceType: dto.resource_type,
    resourceId: dto.resource_id,
    participantType: dto.participant_type,
    role: dto.role,
    isOwner: dto.is_owner,
    userId: dto.user_id,
    employeeId: dto.employee_id,
    name: dto.name,
    createdAt: dto.created_at,
  };
}

function toShare(dto: z.infer<typeof shareSchema>): ShareLink {
  return {
    id: dto.id,
    resourceType: dto.resource_type,
    resourceId: dto.resource_id,
    role: dto.role,
    createdByUserId: dto.created_by_user_id,
    isActive: dto.is_active,
    expiresAt: dto.expires_at,
    revokedAt: dto.revoked_at,
    createdAt: dto.created_at,
  };
}

function toActivity(dto: z.infer<typeof activitySchema>): ResourceActivity {
  return {
    id: dto.id,
    kind: dto.kind,
    actorType: dto.actor_type,
    actorId: dto.actor_id,
    actorName: dto.actor_name,
    summary: dto.summary,
    isOwn: dto.is_own,
    createdAt: dto.created_at,
  };
}

// --- Error translation ---------------------------------------------------

function toError(error: unknown, fallback: string): ResourceCollaborationError {
  if (error instanceof ResourceCollaborationError) return error;
  if (error instanceof ApiError) {
    if (error.isNetworkError) {
      return new ResourceCollaborationError("unavailable", error.message);
    }
    if (error.status === 404) {
      return new ResourceCollaborationError(
        "not_found",
        "That resource doesn't exist, or you're not a participant."
      );
    }
    if (error.status === 403) {
      return new ResourceCollaborationError("forbidden", error.message);
    }
    if (error.status === 409) {
      return new ResourceCollaborationError("conflict", error.message);
    }
    if (error.status === 410) {
      return new ResourceCollaborationError(
        "invalid",
        "That share link has expired or been revoked."
      );
    }
    if (error.status === 422) {
      return Array.isArray(error.details)
        ? new ResourceCollaborationError("unknown", fallback)
        : new ResourceCollaborationError("invalid", error.message);
    }
    if (error.status >= 500) {
      return new ResourceCollaborationError("unavailable", error.message);
    }
    return new ResourceCollaborationError("unknown", error.message);
  }
  return new ResourceCollaborationError("unknown", fallback);
}

function base(rt: CollaborationResourceType, rid: string): string {
  return `/collaboration/${rt}/${encodeURIComponent(rid)}`;
}

// --- Service -------------------------------------------------------------

export const resourceCollaborationService = {
  async access(
    rt: CollaborationResourceType,
    rid: string
  ): Promise<ResourceAccess> {
    try {
      const raw = await request<unknown>(`${base(rt, rid)}/access`);
      const dto = accessSchema.parse(raw);
      return {
        resourceType: dto.resource_type,
        resourceId: dto.resource_id,
        role: dto.role,
        isOwner: dto.is_owner,
      };
    } catch (error) {
      throw toError(error, "Unable to check access.");
    }
  },

  async participants(
    rt: CollaborationResourceType,
    rid: string
  ): Promise<ResourceParticipant[]> {
    try {
      const raw = await request<unknown>(`${base(rt, rid)}/participants`);
      return z.array(participantSchema).parse(raw).map(toParticipant);
    } catch (error) {
      throw toError(error, "Unable to load participants.");
    }
  },

  async addParticipant(
    rt: CollaborationResourceType,
    rid: string,
    input: AddParticipantInput
  ): Promise<ResourceParticipant> {
    try {
      const raw = await request<unknown>(`${base(rt, rid)}/participants`, {
        method: "POST",
        body: {
          participant_type: input.participantType,
          role: input.role,
          user_id: input.userId ?? null,
          employee_id: input.employeeId ?? null,
        },
      });
      return toParticipant(participantSchema.parse(raw));
    } catch (error) {
      throw toError(error, "That participant couldn't be added.");
    }
  },

  async updateRole(
    rt: CollaborationResourceType,
    rid: string,
    participantId: string,
    role: CollaborationRole
  ): Promise<ResourceParticipant> {
    try {
      const raw = await request<unknown>(
        `${base(rt, rid)}/participants/${encodeURIComponent(participantId)}`,
        { method: "PATCH", body: { role } }
      );
      return toParticipant(participantSchema.parse(raw));
    } catch (error) {
      throw toError(error, "That role couldn't be changed.");
    }
  },

  async removeParticipant(
    rt: CollaborationResourceType,
    rid: string,
    participantId: string
  ): Promise<void> {
    try {
      await request<void>(
        `${base(rt, rid)}/participants/${encodeURIComponent(participantId)}`,
        { method: "DELETE" }
      );
    } catch (error) {
      throw toError(error, "That participant couldn't be removed.");
    }
  },

  async shares(
    rt: CollaborationResourceType,
    rid: string
  ): Promise<ShareLink[]> {
    try {
      const raw = await request<unknown>(`${base(rt, rid)}/shares`);
      return z.array(shareSchema).parse(raw).map(toShare);
    } catch (error) {
      throw toError(error, "Unable to load share links.");
    }
  },

  async createShare(
    rt: CollaborationResourceType,
    rid: string,
    input: CreateShareInput
  ): Promise<CreatedShareLink> {
    try {
      const raw = await request<unknown>(`${base(rt, rid)}/shares`, {
        method: "POST",
        body: {
          role: input.role,
          expires_in_days: input.expiresInDays ?? null,
        },
      });
      const dto = createdShareSchema.parse(raw);
      return { ...toShare(dto), token: dto.token, path: dto.path };
    } catch (error) {
      throw toError(error, "That share link couldn't be created.");
    }
  },

  async revokeShare(
    rt: CollaborationResourceType,
    rid: string,
    shareId: string
  ): Promise<void> {
    try {
      await request<void>(
        `${base(rt, rid)}/shares/${encodeURIComponent(shareId)}`,
        { method: "DELETE" }
      );
    } catch (error) {
      throw toError(error, "That share link couldn't be revoked.");
    }
  },

  async redeem(token: string): Promise<ResourceParticipant> {
    try {
      const raw = await request<unknown>("/collaboration/shares/redeem", {
        method: "POST",
        body: { token },
      });
      return toParticipant(participantSchema.parse(raw));
    } catch (error) {
      throw toError(error, "That link couldn't be redeemed.");
    }
  },

  async activity(
    rt: CollaborationResourceType,
    rid: string
  ): Promise<ResourceActivity[]> {
    try {
      const raw = await request<unknown>(`${base(rt, rid)}/activity`);
      return z.array(activitySchema).parse(raw).map(toActivity);
    } catch (error) {
      throw toError(error, "Unable to load activity.");
    }
  },
};

export type ResourceCollaborationService = typeof resourceCollaborationService;
