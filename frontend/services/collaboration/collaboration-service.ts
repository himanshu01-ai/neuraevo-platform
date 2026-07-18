import { MockCollaborationAdapter } from "./mock-adapter";
import type { ApprovalDecision, CollaborationAdapter } from "./types";

/**
 * The app's single entry point to collaboration data. Swapping providers =
 * swapping this one adapter for a Sprint 18 backend adapter; callers (the
 * feature hooks) never change. No fetch/axios/SDKs, no sockets.
 */
const adapter: CollaborationAdapter = new MockCollaborationAdapter();

export const collaborationService = {
  notifications: () => adapter.notifications(),
  notification: (id: string) => adapter.notification(id),
  activity: () => adapter.activity(),
  mentions: () => adapter.mentions(),
  teamActivity: () => adapter.teamActivity(),
  approvals: () => adapter.approvals(),
  counts: () => adapter.counts(),
  markRead: (id: string, read: boolean) => adapter.markRead(id, read),
  markAllRead: () => adapter.markAllRead(),
  setArchived: (id: string, archived: boolean) => adapter.setArchived(id, archived),
  setPinned: (id: string, pinned: boolean) => adapter.setPinned(id, pinned),
  setBookmarked: (id: string, bookmarked: boolean) => adapter.setBookmarked(id, bookmarked),
  setFollowing: (id: string, following: boolean) => adapter.setFollowing(id, following),
  setMuted: (id: string, muted: boolean) => adapter.setMuted(id, muted),
  decide: (decision: ApprovalDecision) => adapter.decide(decision),
};

export type CollaborationService = typeof collaborationService;
