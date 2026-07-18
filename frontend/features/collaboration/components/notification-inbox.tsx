"use client";

import { useCallback } from "react";
import { useCollaborationStore } from "@/store/collaboration";
import { ErrorState } from "@/components/ui/error-state";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useNotifications, useNotificationToggle } from "../hooks/use-collaboration";
import { useFilteredNotifications } from "../hooks/use-filtered-notifications";
import { NotificationFeed } from "../feed/notification-feed";
import { NotificationFilterBar } from "../filters/notification-filters";
import { CollaborationHeader } from "./collaboration-header";
import { FeedLoading } from "./collaboration-loading";

/**
 * The Inbox: a single-column, full-width feed for working through
 * notifications, with the quick actions on each row and no inspector. Reuses
 * the same feed and filters as the center; the difference is focus, not data —
 * this screen is for triage, so density (compact/comfortable) matters most
 * here.
 *
 * Selecting a row on the inbox marks it read in place rather than opening an
 * inspector — the whole screen is the list.
 */
export function NotificationInbox() {
  const feed = useNotifications();
  const filters = useCollaborationStore((s) => s.filters);
  const viewMode = useCollaborationStore((s) => s.viewMode);
  const toggle = useNotificationToggle();

  const rows = useFilteredNotifications(feed.data, filters);
  const toggleMutate = toggle.mutate;

  const handleToggle = useCallback(
    (id: string, field: "read" | "archived" | "pinned" | "bookmarked" | "following" | "muted", value: boolean) =>
      toggleMutate({ id, field, value }),
    [toggleMutate]
  );

  const handleSelect = useCallback(
    (id: string) => {
      const row = feed.data?.find((n) => n.id === id);
      if (row && !row.read) toggleMutate({ id, field: "read", value: true });
    },
    [feed.data, toggleMutate]
  );

  return (
    <WorkspaceContent>
      <Reveal>
        <CollaborationHeader
          title="Inbox"
          description="Work through your notifications — mark read, archive, pin, or follow up."
        />
      </Reveal>

      <div className="mt-4">
        <NotificationFilterBar />
      </div>

      <div className="mt-4 max-w-4xl">
        {feed.isError ? (
          <ErrorState
            title="Couldn't load your inbox"
            description="Your notifications couldn't be loaded. Try again in a moment."
            onRetry={() => void feed.refetch()}
          />
        ) : feed.isPending ? (
          <FeedLoading />
        ) : (
          <NotificationFeed
            notifications={rows}
            selectedId={null}
            onSelect={handleSelect}
            onToggle={handleToggle}
            compact={viewMode === "compact"}
            disabled={toggle.isPending}
            emptyTitle={feed.data.length === 0 ? "Inbox zero" : "No notifications match"}
            emptyDescription={
              feed.data.length === 0 ? "You've cleared everything. Nice." : "Try a different word, or clear the filters."
            }
          />
        )}
      </div>
    </WorkspaceContent>
  );
}
