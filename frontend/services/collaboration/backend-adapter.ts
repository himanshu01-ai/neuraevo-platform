/**
 * Real collaboration adapter, backed by the FastAPI Collaboration Platform
 * (Sprint 20). Implements the same `CollaborationAdapter` seam as the mock, so
 * no caller changes.
 *
 *   GET   /collaboration/notifications                 the inbox
 *   GET   /collaboration/notifications/{id}            one notification
 *   PATCH /collaboration/notifications/{id}            toggle a quick-action flag
 *   POST  /collaboration/notifications/read-all        clear the unread state
 *   GET   /collaboration/notifications/counts          badge tallies
 *   GET   /collaboration/activity?scope=mine|mentions|all   the feeds
 *
 * Notifications are *real* here: they are raised by the platform when a
 * participant is added or someone joins a shared resource. Approvals answer
 * empty and `decide` refuses — the human-approval engine is not connected to
 * this surface yet, and an empty inbox is the truth (the same honest stance the
 * task adapter takes). Ownership and auth are the backend's; `http.ts` attaches
 * and refreshes the token.
 */

import { ApiError, request } from "../http";
import {
  activityListSchema,
  countsSchema,
  notificationListSchema,
  toActivityEvent,
  toCollaborationCounts,
  toNotificationDetail,
  toNotificationSummary,
} from "./mapping";
import {
  CollaborationError,
  type ActivityEvent,
  type ApprovalDecision,
  type CollaborationAdapter,
  type CollaborationApproval,
  type CollaborationCounts,
  type NotificationDetail,
  type NotificationSummary,
} from "./types";

/** Map a transport-level `ApiError` onto the collaboration vocabulary. */
function toCollaborationError(error: unknown, fallback: string): CollaborationError {
  if (error instanceof CollaborationError) return error;
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return new CollaborationError("not_found", "That notification doesn't exist.");
    }
    return new CollaborationError("unknown", error.message || fallback);
  }
  return new CollaborationError("unknown", fallback);
}

async function getNotifications(): Promise<NotificationSummary[]> {
  const raw = await request<unknown>("/collaboration/notifications");
  return notificationListSchema.parse(raw).map(toNotificationSummary);
}

async function patchNotification(
  id: string,
  body: Record<string, boolean>
): Promise<NotificationSummary> {
  const raw = await request<unknown>(
    `/collaboration/notifications/${encodeURIComponent(id)}`,
    { method: "PATCH", body }
  );
  return toNotificationDetail(
    notificationListSchema.element.parse(raw)
  );
}

async function activityFeed(
  scope: "mine" | "mentions" | "all"
): Promise<ActivityEvent[]> {
  const raw = await request<unknown>(`/collaboration/activity?scope=${scope}`);
  return activityListSchema.parse(raw).map(toActivityEvent);
}

export class BackendCollaborationAdapter implements CollaborationAdapter {
  // --- Reads -------------------------------------------------------------

  async notifications(): Promise<NotificationSummary[]> {
    try {
      return await getNotifications();
    } catch (error) {
      throw toCollaborationError(error, "Unable to load notifications.");
    }
  }

  async notification(id: string): Promise<NotificationDetail> {
    try {
      const raw = await request<unknown>(
        `/collaboration/notifications/${encodeURIComponent(id)}`
      );
      return toNotificationDetail(notificationListSchema.element.parse(raw));
    } catch (error) {
      throw toCollaborationError(error, "Unable to load that notification.");
    }
  }

  async activity(): Promise<ActivityEvent[]> {
    try {
      return await activityFeed("mine");
    } catch (error) {
      throw toCollaborationError(error, "Unable to load your activity.");
    }
  }

  async mentions(): Promise<ActivityEvent[]> {
    try {
      return await activityFeed("mentions");
    } catch (error) {
      throw toCollaborationError(error, "Unable to load mentions.");
    }
  }

  async teamActivity(): Promise<ActivityEvent[]> {
    try {
      return await activityFeed("all");
    } catch (error) {
      throw toCollaborationError(error, "Unable to load team activity.");
    }
  }

  async approvals(): Promise<CollaborationApproval[]> {
    // The approval engine is not connected to this surface yet — an empty inbox
    // is the truth, and the screen renders an honest empty state for it.
    return [];
  }

  async counts(): Promise<CollaborationCounts> {
    try {
      const raw = await request<unknown>("/collaboration/notifications/counts");
      return toCollaborationCounts(countsSchema.parse(raw));
    } catch (error) {
      throw toCollaborationError(error, "Unable to load counts.");
    }
  }

  // --- Mutations ---------------------------------------------------------

  async markRead(id: string, read: boolean): Promise<NotificationSummary> {
    try {
      return await patchNotification(id, { read });
    } catch (error) {
      throw toCollaborationError(error, "That couldn't be updated.");
    }
  }

  async markAllRead(): Promise<NotificationSummary[]> {
    try {
      const raw = await request<unknown>(
        "/collaboration/notifications/read-all",
        { method: "POST", body: {} }
      );
      return notificationListSchema.parse(raw).map(toNotificationSummary);
    } catch (error) {
      throw toCollaborationError(error, "Those couldn't be marked read.");
    }
  }

  async setArchived(id: string, archived: boolean): Promise<NotificationSummary> {
    try {
      return await patchNotification(id, { archived });
    } catch (error) {
      throw toCollaborationError(error, "That couldn't be updated.");
    }
  }

  async setPinned(id: string, pinned: boolean): Promise<NotificationSummary> {
    try {
      return await patchNotification(id, { pinned });
    } catch (error) {
      throw toCollaborationError(error, "That couldn't be updated.");
    }
  }

  async setBookmarked(id: string, bookmarked: boolean): Promise<NotificationSummary> {
    try {
      return await patchNotification(id, { bookmarked });
    } catch (error) {
      throw toCollaborationError(error, "That couldn't be updated.");
    }
  }

  async setFollowing(id: string, following: boolean): Promise<NotificationSummary> {
    try {
      return await patchNotification(id, { following });
    } catch (error) {
      throw toCollaborationError(error, "That couldn't be updated.");
    }
  }

  async setMuted(id: string, muted: boolean): Promise<NotificationSummary> {
    try {
      return await patchNotification(id, { muted });
    } catch (error) {
      throw toCollaborationError(error, "That couldn't be updated.");
    }
  }

  async decide(_decision: ApprovalDecision): Promise<CollaborationApproval> {
    throw new CollaborationError(
      "unknown",
      "Approvals aren't connected to the platform yet."
    );
  }
}
