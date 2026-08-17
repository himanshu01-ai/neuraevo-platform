import { dateValue } from "@/utils/format";
import { ACTIVITY, APPROVALS, NOTIFICATIONS } from "./fixtures";
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

/**
 * Deterministic in-browser mock of a collaboration backend. No network, no
 * clock, no randomness, and no socket. Writes go to localStorage to simulate
 * server persistence so a read/pin/bookmark survives a reload — the same
 * approach `MockConversationsAdapter` (17.9) and `MockTasksAdapter` (17.7) use.
 *
 * This mock stores descriptions of what the platform *would have* raised. It
 * emits nothing on its own: no notification arrives after load, no count ticks,
 * no feed grows. State changes only when the user acts — marking read, pinning,
 * deciding an approval — and even then this records the request; the real
 * platform is what would raise the events.
 */

const NOTIFICATIONS_KEY = "neuraevo.mock.collaboration.notifications";
const APPROVALS_KEY = "neuraevo.mock.collaboration.approvals";
const LATENCY_MS = 350;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

/** Structured clone via JSON — fixtures and stored rows are plain data. */
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function read<T>(key: string, seed: () => T): T {
  if (typeof window === "undefined") return seed();
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return seed();
    const parsed = JSON.parse(raw) as T;
    return parsed ?? seed();
  } catch {
    return seed();
  }
}

function write(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* quota or private mode — the change simply doesn't persist */
  }
}

const readNotifications = (): NotificationDetail[] => {
  const rows = read<NotificationDetail[]>(NOTIFICATIONS_KEY, () => copy(NOTIFICATIONS));
  return Array.isArray(rows) ? rows : copy(NOTIFICATIONS);
};
const writeNotifications = (rows: NotificationDetail[]) => write(NOTIFICATIONS_KEY, rows);

const readApprovals = (): CollaborationApproval[] => {
  const rows = read<CollaborationApproval[]>(APPROVALS_KEY, () => copy(APPROVALS));
  return Array.isArray(rows) ? rows : copy(APPROVALS);
};
const writeApprovals = (rows: CollaborationApproval[]) => write(APPROVALS_KEY, rows);

/** Newest first, the order every feed reads. */
const byNewest = <T extends { createdAt: string }>(rows: T[]): T[] =>
  [...rows].sort((a, b) => dateValue(b.createdAt) - dateValue(a.createdAt));

function toSummary(row: NotificationDetail): NotificationSummary {
  const { relatedEntities: _re, history: _h, comments: _c, watchers: _w, ...summary } = row;
  return summary;
}

export class MockCollaborationAdapter implements CollaborationAdapter {
  async notifications(): Promise<NotificationSummary[]> {
    await delay();
    return byNewest(readNotifications().map(toSummary));
  }

  async notification(id: string): Promise<NotificationDetail> {
    await delay();
    const row = readNotifications().find((n) => n.id === id);
    if (!row) throw new CollaborationError("not_found", "That notification doesn't exist.");
    return copy(row);
  }

  async activity(): Promise<ActivityEvent[]> {
    await delay();
    // The personal feed: what the owner did or was tagged in.
    return byNewest(copy(ACTIVITY).filter((e) => e.isOwn));
  }

  async mentions(): Promise<ActivityEvent[]> {
    await delay();
    return byNewest(copy(ACTIVITY).filter((e) => e.kind === "mentioned"));
  }

  async teamActivity(): Promise<ActivityEvent[]> {
    await delay();
    return byNewest(copy(ACTIVITY));
  }

  async approvals(): Promise<CollaborationApproval[]> {
    await delay();
    return byNewest(readApprovals());
  }

  /**
   * The tallies the header and nav badges show. Counted here from the stored
   * rows so they always agree with the feeds; the real backend would carry
   * these, and the UI would still never recompute them.
   */
  async counts(): Promise<CollaborationCounts> {
    await delay();
    const rows = readNotifications();
    const live = rows.filter((n) => !n.archived);
    return {
      unread: live.filter((n) => !n.read).length,
      mentions: live.filter((n) => n.isMention && !n.read).length,
      pendingApprovals: readApprovals().filter((a) => a.status === "PENDING").length,
      bookmarked: rows.filter((n) => n.bookmarked).length,
    };
  }

  // ---- mutations -----------------------------------------------------

  /** Applies a change to one notification and returns its fresh summary. */
  private mutate(id: string, apply: (row: NotificationDetail) => NotificationDetail): NotificationSummary {
    const rows = readNotifications();
    const index = rows.findIndex((n) => n.id === id);
    const row = index >= 0 ? rows[index] : undefined;
    if (!row) throw new CollaborationError("not_found", "That notification doesn't exist.");
    const next = apply(row);
    rows[index] = next;
    writeNotifications(rows);
    return toSummary(copy(next));
  }

  async markRead(id: string, read: boolean): Promise<NotificationSummary> {
    await delay();
    return this.mutate(id, (row) => ({ ...row, read }));
  }

  async markAllRead(): Promise<NotificationSummary[]> {
    await delay();
    // Only what's on the board is cleared; archived rows stay as they were.
    const rows = readNotifications().map((row) => (row.archived ? row : { ...row, read: true }));
    writeNotifications(rows);
    return byNewest(rows.map(toSummary));
  }

  async setArchived(id: string, archived: boolean): Promise<NotificationSummary> {
    await delay();
    return this.mutate(id, (row) => ({ ...row, archived }));
  }

  async setPinned(id: string, pinned: boolean): Promise<NotificationSummary> {
    await delay();
    return this.mutate(id, (row) => ({ ...row, pinned }));
  }

  async setBookmarked(id: string, bookmarked: boolean): Promise<NotificationSummary> {
    await delay();
    return this.mutate(id, (row) => ({ ...row, bookmarked }));
  }

  async setFollowing(id: string, following: boolean): Promise<NotificationSummary> {
    await delay();
    return this.mutate(id, (row) => ({ ...row, following }));
  }

  async setMuted(id: string, muted: boolean): Promise<NotificationSummary> {
    await delay();
    return this.mutate(id, (row) => ({ ...row, muted }));
  }

  async decide(decision: ApprovalDecision): Promise<CollaborationApproval> {
    await delay();
    const rows = readApprovals();
    const index = rows.findIndex((a) => a.id === decision.approvalId);
    const approval = index >= 0 ? rows[index] : undefined;
    if (!approval) throw new CollaborationError("not_found", "That approval doesn't exist.");
    if (approval.status !== "PENDING")
      throw new CollaborationError("already_decided", "That approval has already been decided.");

    const next: CollaborationApproval = {
      ...approval,
      status: decision.status,
      comment: decision.comment.trim() || null,
    };
    rows[index] = next;
    writeApprovals(rows);
    return copy(next);
  }
}
