/**
 * Public surface of the collaboration service. Features import from here and
 * never from the adapter or fixtures directly — the seam Sprint 18 swaps.
 */
export { collaborationService, type CollaborationService } from "./collaboration-service";
export { collaborationKeys } from "./keys";
export {
  ACTIVITY_KINDS,
  ACTIVITY_KIND_LABEL,
  ACTIVITY_KIND_TONE,
  CollaborationError,
  EMPTY_NOTIFICATION_FILTERS,
  NOTIFICATION_ACTIONS,
  NOTIFICATION_TYPES,
  NOTIFICATION_TYPE_LABEL,
  NOTIFICATION_TYPE_TONE,
  type Actor,
  type ActivityEvent,
  type ActivityKind,
  type ApprovalDecision,
  type CollaborationAdapter,
  type CollaborationApproval,
  type CollaborationCounts,
  type CollaborationErrorCode,
  type Comment,
  type ConversationRef,
  type EmployeeRef,
  type EntityKind,
  type MemoryRef,
  type NotificationAction,
  type NotificationDetail,
  type NotificationFilters,
  type NotificationHistoryEntry,
  type NotificationSummary,
  type NotificationType,
  type RelatedEntity,
  type TaskRef,
  type WorkflowRef,
} from "./types";
