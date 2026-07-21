import { describe, expect, it } from "vitest";
import {
  toActivityEvent,
  toCollaborationCounts,
  toNotificationDetail,
  toNotificationSummary,
  type ActivityDTO,
  type CountsDTO,
  type NotificationDTO,
} from "./mapping";

const notification: NotificationDTO = {
  id: "n1",
  type: "task",
  title: "You were added to a task",
  description: "You now have editor access.",
  resource_type: "task",
  resource_id: "t1",
  actor_type: "user",
  actor_id: "u1",
  actor_name: "Olivia Owner",
  priority: "high",
  read: false,
  archived: false,
  pinned: false,
  bookmarked: false,
  following: false,
  muted: false,
  created_at: "2026-07-22T10:00:00Z",
};

describe("collaboration notification mapping", () => {
  it("maps a backend notification to the summary projection", () => {
    const summary = toNotificationSummary(notification);
    expect(summary.type).toBe("task");
    // Backend priority is lowercase; the projection is uppercase.
    expect(summary.priority).toBe("HIGH");
    expect(summary.source).toEqual({
      id: "u1",
      name: "Olivia Owner",
      kind: "user",
      detail: "",
    });
    // Fields the backend doesn't carry yet are honest, not invented.
    expect(summary.primaryEntity).toBeNull();
    expect(summary.isMention).toBe(false);
  });

  it("falls back to a system actor when none is named", () => {
    const summary = toNotificationSummary({
      ...notification,
      actor_type: null,
      actor_id: null,
      actor_name: null,
    });
    expect(summary.source.kind).toBe("system");
    expect(summary.source.name).toBe("System");
  });

  it("narrows an unknown type to system", () => {
    const summary = toNotificationSummary({ ...notification, type: "bogus" });
    expect(summary.type).toBe("system");
  });

  it("detail carries empty extras the platform doesn't back yet", () => {
    const detail = toNotificationDetail(notification);
    expect(detail.comments).toEqual([]);
    expect(detail.watchers).toEqual([]);
    expect(detail.relatedEntities).toEqual([]);
    expect(detail.history).toEqual([]);
  });
});

describe("collaboration activity mapping", () => {
  const base: ActivityDTO = {
    id: "a1",
    resource_type: "task",
    resource_id: "t1",
    kind: "participant_added",
    actor_type: "user",
    actor_id: "u1",
    actor_name: "Olivia Owner",
    summary: "Added Cody as viewer",
    is_own: true,
    created_at: "2026-07-22T10:00:00Z",
  };

  it("folds collaboration-specific kinds onto the projected vocabulary", () => {
    expect(toActivityEvent(base).kind).toBe("assigned");
    expect(toActivityEvent({ ...base, kind: "share_revoked" }).kind).toBe("archived");
    expect(toActivityEvent({ ...base, kind: "role_changed" }).kind).toBe("updated");
    expect(toActivityEvent({ ...base, kind: "completed" }).kind).toBe("completed");
  });

  it("carries the isOwn flag and actor through", () => {
    const event = toActivityEvent(base);
    expect(event.isOwn).toBe(true);
    expect(event.actor.name).toBe("Olivia Owner");
  });
});

describe("collaboration counts mapping", () => {
  it("renames pending_approvals to the projection's camelCase", () => {
    const dto: CountsDTO = { unread: 3, mentions: 0, pending_approvals: 0, bookmarked: 1 };
    expect(toCollaborationCounts(dto)).toEqual({
      unread: 3,
      mentions: 0,
      pendingApprovals: 0,
      bookmarked: 1,
    });
  });
});
