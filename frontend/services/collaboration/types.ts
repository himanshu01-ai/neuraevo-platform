/**
 * Collaboration & notification contracts — provider-independent. The
 * collaboration feature depends only on these types and the
 * `CollaborationAdapter` interface, never on a concrete provider. Sprint 17.10
 * ships a deterministic mock adapter; a real backend adapter drops in later
 * with zero changes to callers.
 *
 * ## What is real, and what this layer is projecting
 *
 * The platform emits notification *events* already — Sprint 5's
 * `WorkflowNotificationEvent` (`WORKFLOW_STARTED`, `APPROVAL_REQUIRED`, …) and
 * the task lifecycle are the closest things behind this — but there is **no
 * notification-center table, no activity log, no comment/mention/follow/bookmark
 * store** today. So every shape below is **projection**: it names what a
 * collaboration surface would show and leaves the wire mapping for Sprint 18.
 * Where a vocabulary already exists in the backend (`Priority`,
 * `ApprovalStatus`) it is imported from `types/domain.ts` and never redefined.
 *
 * Nothing here sends, pushes, subscribes, or polls a socket. It describes what
 * the platform would say happened; the backend is what would say it.
 */

import type { ApprovalStatus, Priority, StatusTone } from "@/types/domain";

// =====================================================================
// Notification vocabulary (projection)
// =====================================================================

/**
 * **Projection.** What a notification is *about* — which subsystem raised it.
 * Ordered by how the platform's own domain model reads (work first, then the
 * collaboration and system layers), not alphabetically; filters and legends
 * read this order.
 */
export const NOTIFICATION_TYPES = [
  "task",
  "workflow",
  "memory",
  "conversation",
  "approval",
  "employee",
  "system",
] as const;
export type NotificationType = (typeof NOTIFICATION_TYPES)[number];

export const NOTIFICATION_TYPE_LABEL: Record<NotificationType, string> = {
  task: "Task",
  workflow: "Workflow",
  memory: "Memory",
  conversation: "Conversation",
  approval: "Approval",
  employee: "AI employee",
  system: "System",
};

/**
 * Type → tone. Colour resolves through the one `StatusTone` scale, so a
 * notification reads in the same five colours as every other status. Approval
 * is the one that asks for a decision, so it carries the warning tone the
 * approval vocabulary uses elsewhere.
 */
export const NOTIFICATION_TYPE_TONE: Record<NotificationType, StatusTone> = {
  task: "info",
  workflow: "info",
  memory: "neutral",
  conversation: "info",
  approval: "warning",
  employee: "success",
  system: "neutral",
};

// =====================================================================
// Activity vocabulary (projection)
// =====================================================================

/**
 * **Projection.** What happened, in the platform's own verbs. Several mirror
 * events that do exist — `completed`/`approved`/`rejected`/`archived` line up
 * with lifecycle and approval transitions — but the activity *log* that would
 * carry them is not built, so this list is owned here.
 */
export const ACTIVITY_KINDS = [
  "created",
  "updated",
  "assigned",
  "completed",
  "commented",
  "mentioned",
  "approved",
  "rejected",
  "archived",
] as const;
export type ActivityKind = (typeof ACTIVITY_KINDS)[number];

export const ACTIVITY_KIND_LABEL: Record<ActivityKind, string> = {
  created: "Created",
  updated: "Updated",
  assigned: "Assigned",
  completed: "Completed",
  commented: "Commented",
  mentioned: "Mentioned",
  approved: "Approved",
  rejected: "Rejected",
  archived: "Archived",
};

/** Activity → tone, for the dot beside each feed row. */
export const ACTIVITY_KIND_TONE: Record<ActivityKind, StatusTone> = {
  created: "info",
  updated: "info",
  assigned: "info",
  completed: "success",
  commented: "neutral",
  mentioned: "warning",
  approved: "success",
  rejected: "danger",
  archived: "neutral",
};

// =====================================================================
// Actors & references — identity only; the owning module owns the rest
// =====================================================================

/** Who did something, or who a notification is from. Identity only. */
export interface Actor {
  id: string;
  name: string;
  /** `user` is the human owner; `employee` is an AI employee; `system` is the platform. */
  kind: "user" | "employee" | "system";
  /** One line under the name — a role title or "Workspace owner". */
  detail: string;
}

export interface EmployeeRef {
  employeeId: string;
  employeeName: string;
  roleTitle: string;
}

export interface WorkflowRef {
  workflowId: string;
  workflowName: string;
}

export interface TaskRef {
  taskId: string;
  /** The id a person quotes — the backend's own `task_id`. */
  businessId: string;
  taskName: string;
}

export interface MemoryRef {
  memoryId: string;
  title: string;
}

export interface ConversationRef {
  conversationId: string;
  title: string;
  employeeName: string;
}

/**
 * A record a notification or activity points at, tagged by which module owns
 * it. The inspector renders each through one reference card and links into the
 * owning workspace — the same identity-only rule references follow everywhere.
 */
export type RelatedEntity =
  | { kind: "employee"; employee: EmployeeRef }
  | { kind: "workflow"; workflow: WorkflowRef }
  | { kind: "task"; task: TaskRef }
  | { kind: "memory"; memory: MemoryRef }
  | { kind: "conversation"; conversation: ConversationRef };

/** The module a `RelatedEntity` belongs to — handy for filtering and icons. */
export type EntityKind = RelatedEntity["kind"];

// =====================================================================
// Quick actions (projection, UI only)
// =====================================================================

/**
 * **Projection.** The controls a notification offers. `mark_read` toggles read
 * state; `archive` files it; the rest are the collaboration affordances the
 * spec calls for. Every one is UI only — nothing is sent.
 */
export const NOTIFICATION_ACTIONS = ["mark_read", "archive", "pin", "bookmark", "follow", "mute"] as const;
export type NotificationAction = (typeof NOTIFICATION_ACTIONS)[number];

// =====================================================================
// Comments (projection)
// =====================================================================

export interface Comment {
  id: string;
  actor: Actor;
  body: string;
  createdAt: string;
}

// =====================================================================
// Notification
// =====================================================================

/** What the feed row needs. */
export interface NotificationSummary {
  id: string;
  type: NotificationType;
  title: string;
  description: string;
  /** Who or what raised it. */
  source: Actor;
  createdAt: string;
  priority: Priority;
  read: boolean;
  archived: boolean;
  // ---- collaboration state (projection) ----
  pinned: boolean;
  bookmarked: boolean;
  following: boolean;
  muted: boolean;
  /** The one record this notification is primarily about, for the row's chip. */
  primaryEntity: RelatedEntity | null;
  /** True when the source or body @-mentions the owner — powers the Mentions screen. */
  isMention: boolean;
}

/** Everything the inspector shows for one notification. */
export interface NotificationDetail extends NotificationSummary {
  /** Every record this notification touches, primary first. */
  relatedEntities: RelatedEntity[];
  /** What has happened to this notification and its subject, newest last. */
  history: NotificationHistoryEntry[];
  /** Discussion attached to the notification's subject. Mock only. */
  comments: Comment[];
  /** People watching this subject. Identity only. */
  watchers: Actor[];
}

/** One line in a notification's own audit trail. */
export interface NotificationHistoryEntry {
  id: string;
  kind: ActivityKind;
  summary: string;
  actor: Actor;
  createdAt: string;
}

// =====================================================================
// Activity feed
// =====================================================================

/** One event in the activity or team feed. */
export interface ActivityEvent {
  id: string;
  kind: ActivityKind;
  actor: Actor;
  /** One line naming what happened. Fixture copy — nothing is inferred. */
  summary: string;
  /** The record the event concerns, when it concerns one. */
  entity: RelatedEntity | null;
  createdAt: string;
  /** True for events the owner did or was tagged in — the personal Activity feed. */
  isOwn: boolean;
}

// =====================================================================
// Approvals (collaboration view)
// =====================================================================

/**
 * An approval as the inbox shows it. Mirrors the task board's `Approval` shape
 * (`services/tasks`) so Sprint 18 can back both from one endpoint, but stays
 * self-contained here — collaboration doesn't reach into the task module.
 */
export interface CollaborationApproval {
  id: string;
  title: string;
  description: string;
  status: ApprovalStatus;
  priority: Priority;
  requestedBy: Actor;
  createdAt: string;
  /** What needs the sign-off. */
  entity: RelatedEntity | null;
  /** The reviewer's note, once there is one. */
  comment: string | null;
}

/** What the UI sends when a reviewer decides. UI only — nothing runs. */
export interface ApprovalDecision {
  approvalId: string;
  status: Extract<ApprovalStatus, "APPROVED" | "REJECTED">;
  comment: string;
}

// =====================================================================
// Counts — carried, never recomputed by the UI
// =====================================================================

/** The tallies the header and nav badges show. Carried from the platform. */
export interface CollaborationCounts {
  unread: number;
  mentions: number;
  pendingApprovals: number;
  bookmarked: number;
}

// =====================================================================
// Filters
// =====================================================================

/** `"ALL"` is the unset state for each facet — never a real value. */
export interface NotificationFilters {
  search: string;
  unreadOnly: boolean;
  type: NotificationType | "ALL";
  priority: Priority | "ALL";
  source: EntityKind | "ALL";
  /** ISO days, inclusive. Empty string means unbounded. */
  fromDate: string;
  toDate: string;
}

export const EMPTY_NOTIFICATION_FILTERS: NotificationFilters = {
  search: "",
  unreadOnly: false,
  type: "ALL",
  priority: "ALL",
  source: "ALL",
  fromDate: "",
  toDate: "",
};

// =====================================================================
// Errors & the adapter seam
// =====================================================================

export type CollaborationErrorCode = "not_found" | "invalid_decision" | "already_decided" | "unknown";

export class CollaborationError extends Error {
  code: CollaborationErrorCode;
  constructor(code: CollaborationErrorCode, message: string) {
    super(message);
    this.name = "CollaborationError";
    this.code = code;
  }
}

/**
 * The single seam every collaboration backend must implement. `notifications`,
 * `activity`, `mentions` and `approvals` are the four feeds; the mutations
 * carry the quick actions. Sprint 18 replaces the mock with a real adapter and
 * no caller changes.
 */
export interface CollaborationAdapter {
  notifications(): Promise<NotificationSummary[]>;
  notification(id: string): Promise<NotificationDetail>;
  activity(): Promise<ActivityEvent[]>;
  /** The subset of activity the owner was tagged in. */
  mentions(): Promise<ActivityEvent[]>;
  /** Everyone's activity — the team feed. */
  teamActivity(): Promise<ActivityEvent[]>;
  approvals(): Promise<CollaborationApproval[]>;
  counts(): Promise<CollaborationCounts>;

  markRead(id: string, read: boolean): Promise<NotificationSummary>;
  markAllRead(): Promise<NotificationSummary[]>;
  setArchived(id: string, archived: boolean): Promise<NotificationSummary>;
  setPinned(id: string, pinned: boolean): Promise<NotificationSummary>;
  setBookmarked(id: string, bookmarked: boolean): Promise<NotificationSummary>;
  setFollowing(id: string, following: boolean): Promise<NotificationSummary>;
  setMuted(id: string, muted: boolean): Promise<NotificationSummary>;
  decide(decision: ApprovalDecision): Promise<CollaborationApproval>;
}
