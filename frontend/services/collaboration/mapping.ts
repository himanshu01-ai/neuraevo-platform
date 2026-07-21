/**
 * Wire mapping for the collaboration backend (Sprint 20).
 *
 * Turns the FastAPI Collaboration Platform's DTOs into the notification/activity
 * projection the feature already renders, so the backend adapter drops in behind
 * the same `CollaborationAdapter` seam with no caller change. Where the backend
 * does not yet carry a projected field — a notification's related-entity chip,
 * its comments and watchers — the mapping is honest about it (null / empty)
 * rather than inventing data; those land with the comment and approval slices.
 */

import { z } from "zod";
import type { Priority } from "@/types/domain";
import type {
  Actor,
  ActivityEvent,
  ActivityKind,
  NotificationDetail,
  NotificationSummary,
  NotificationType,
  CollaborationCounts,
} from "./types";

// --- Backend DTO schemas -------------------------------------------------

const notificationSchema = z.object({
  id: z.string(),
  type: z.string(),
  title: z.string(),
  description: z.string(),
  resource_type: z.string().nullable(),
  resource_id: z.string().nullable(),
  actor_type: z.string().nullable(),
  actor_id: z.string().nullable(),
  actor_name: z.string().nullable(),
  priority: z.string(),
  read: z.boolean(),
  archived: z.boolean(),
  pinned: z.boolean(),
  bookmarked: z.boolean(),
  following: z.boolean(),
  muted: z.boolean(),
  created_at: z.string(),
});

export const notificationListSchema = z.array(notificationSchema);
export type NotificationDTO = z.infer<typeof notificationSchema>;

const activitySchema = z.object({
  id: z.string(),
  resource_type: z.string(),
  resource_id: z.string(),
  kind: z.string(),
  actor_type: z.string(),
  actor_id: z.string().nullable(),
  actor_name: z.string(),
  summary: z.string(),
  is_own: z.boolean(),
  created_at: z.string(),
});

export const activityListSchema = z.array(activitySchema);
export type ActivityDTO = z.infer<typeof activitySchema>;

export const countsSchema = z.object({
  unread: z.number(),
  mentions: z.number(),
  pending_approvals: z.number(),
  bookmarked: z.number(),
});
export type CountsDTO = z.infer<typeof countsSchema>;

// --- Value mapping -------------------------------------------------------

const NOTIFICATION_TYPES: readonly NotificationType[] = [
  "task",
  "workflow",
  "memory",
  "conversation",
  "approval",
  "employee",
  "system",
];

/** A backend type string, narrowed to the projection's vocabulary. */
function toNotificationType(value: string): NotificationType {
  return (NOTIFICATION_TYPES as readonly string[]).includes(value)
    ? (value as NotificationType)
    : "system";
}

/** Backend priority is lowercase; the projection's `Priority` is uppercase. */
function toPriority(value: string): Priority {
  const upper = value.toUpperCase();
  return (["LOW", "MEDIUM", "HIGH", "URGENT"].includes(upper)
    ? upper
    : "MEDIUM") as Priority;
}

function toActorKind(value: string | null): Actor["kind"] {
  return value === "user" || value === "employee" ? value : "system";
}

function toActor(
  actorType: string | null,
  actorId: string | null,
  actorName: string | null
): Actor {
  return {
    id: actorId ?? "system",
    name: actorName ?? "System",
    kind: toActorKind(actorType),
    detail: "",
  };
}

/**
 * Backend activity kinds are a superset of the projection's vocabulary (they add
 * the collaboration-specific verbs). Fold the extras onto the nearest projected
 * kind so the feed's tone dot and label stay meaningful.
 */
const ACTIVITY_KIND_MAP: Record<string, ActivityKind> = {
  created: "created",
  updated: "updated",
  assigned: "assigned",
  completed: "completed",
  commented: "commented",
  mentioned: "mentioned",
  approved: "approved",
  rejected: "rejected",
  archived: "archived",
  participant_added: "assigned",
  joined: "assigned",
  participant_removed: "updated",
  role_changed: "updated",
  shared: "updated",
  share_revoked: "archived",
};

function toActivityKind(value: string): ActivityKind {
  return ACTIVITY_KIND_MAP[value] ?? "updated";
}

// --- Mappers -------------------------------------------------------------

export function toNotificationSummary(dto: NotificationDTO): NotificationSummary {
  return {
    id: dto.id,
    type: toNotificationType(dto.type),
    title: dto.title,
    description: dto.description,
    source: toActor(dto.actor_type, dto.actor_id, dto.actor_name),
    createdAt: dto.created_at,
    priority: toPriority(dto.priority),
    read: dto.read,
    archived: dto.archived,
    pinned: dto.pinned,
    bookmarked: dto.bookmarked,
    following: dto.following,
    muted: dto.muted,
    // The backend notification does not carry the resource's display name, so
    // there is no entity chip yet — the card still reads without one.
    primaryEntity: null,
    isMention: false,
  };
}

export function toNotificationDetail(dto: NotificationDTO): NotificationDetail {
  return {
    ...toNotificationSummary(dto),
    relatedEntities: [],
    history: [],
    comments: [],
    watchers: [],
  };
}

export function toActivityEvent(dto: ActivityDTO): ActivityEvent {
  return {
    id: dto.id,
    kind: toActivityKind(dto.kind),
    actor: toActor(dto.actor_type, dto.actor_id, dto.actor_name),
    summary: dto.summary,
    entity: null,
    createdAt: dto.created_at,
    isOwn: dto.is_own,
  };
}

export function toCollaborationCounts(dto: CountsDTO): CollaborationCounts {
  return {
    unread: dto.unread,
    mentions: dto.mentions,
    pendingApprovals: dto.pending_approvals,
    bookmarked: dto.bookmarked,
  };
}
