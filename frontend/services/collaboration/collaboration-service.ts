import { env } from "@/lib/env";
import { BackendCollaborationAdapter } from "./backend-adapter";
import { MockCollaborationAdapter } from "./mock-adapter";
import type { ApprovalDecision, CollaborationAdapter } from "./types";

/**
 * The app's single entry point to collaboration data, and the only place that
 * knows which adapter is active. Callers (the feature hooks) never import an
 * adapter.
 *
 * Sprint 20 wired the notification center to the real Collaboration Platform:
 * `backend` (default) shows notifications the platform actually raised (a
 * participant added, a shared resource joined); `mock` keeps the Sprint 17.10
 * offline fixtures — richer for surfaces the platform does not yet back
 * (comments, watchers, approvals) — selectable via
 * `NEXT_PUBLIC_COLLABORATION_ADAPTER=mock`.
 */
const adapter: CollaborationAdapter =
  env.NEXT_PUBLIC_COLLABORATION_ADAPTER === "mock"
    ? new MockCollaborationAdapter()
    : new BackendCollaborationAdapter();

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
