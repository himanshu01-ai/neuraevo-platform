"use client";

import { useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { MousePointerSquareDashed } from "lucide-react";
import { useCollaborationStore } from "@/store/collaboration";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import {
  useNotificationDetail,
  useNotifications,
  useNotificationToggle,
} from "../hooks/use-collaboration";
import { useFilteredNotifications } from "../hooks/use-filtered-notifications";
import { NotificationFeed } from "../feed/notification-feed";
import { NotificationFilterBar } from "../filters/notification-filters";
import { CollaborationHeader } from "./collaboration-header";
import { FeedLoading, InspectorLoading } from "./collaboration-loading";
import { cn } from "@/lib/utils";

/**
 * The Notification Center: header and tabs on top, the filtered feed on the
 * left, and the selected notification's inspector on the right — the layout the
 * spec calls for (header, feed, inspector).
 *
 * The inspector is the heavy, optional half of the screen, so it loads on
 * demand. Below `xl` it rides over the feed as a drawer rather than beside it;
 * selecting a row opens it, and the backdrop or Escape closes it. Selecting a
 * row also marks it read — opening a notification is reading it.
 */
const NotificationInspector = dynamic(
  () => import("./notification-inspector").then((m) => m.NotificationInspector),
  { loading: () => <InspectorLoading /> }
);

export function NotificationCenter() {
  const feed = useNotifications();
  const filters = useCollaborationStore((s) => s.filters);
  const selectedId = useCollaborationStore((s) => s.selectedNotificationId);
  const selectNotification = useCollaborationStore((s) => s.selectNotification);

  const detail = useNotificationDetail(selectedId);
  const toggle = useNotificationToggle();

  const rows = useFilteredNotifications(feed.data, filters);

  // A selection outlives the feed it came from.
  useEffect(() => {
    if (!feed.data || selectedId === null) return;
    if (!feed.data.some((n) => n.id === selectedId)) selectNotification(null);
  }, [feed.data, selectedId, selectNotification]);

  const toggleMutate = toggle.mutate;
  const handleToggle = useCallback(
    (id: string, field: "read" | "archived" | "pinned" | "bookmarked" | "following" | "muted", value: boolean) =>
      toggleMutate({ id, field, value }),
    [toggleMutate]
  );

  // Opening a notification reads it.
  const handleSelect = useCallback(
    (id: string) => {
      selectNotification(id);
      const row = feed.data?.find((n) => n.id === id);
      if (row && !row.read) toggleMutate({ id, field: "read", value: true });
    },
    [selectNotification, feed.data, toggleMutate]
  );

  // Escape closes the drawer on small screens.
  useEffect(() => {
    if (selectedId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") selectNotification(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, selectNotification]);

  const feedBody = () => {
    if (feed.isError) {
      return (
        <ErrorState
          title="Couldn't load notifications"
          description="Your notifications couldn't be loaded. Try again in a moment."
          onRetry={() => void feed.refetch()}
        />
      );
    }
    if (feed.isPending) return <FeedLoading />;
    return (
      <NotificationFeed
        notifications={rows}
        selectedId={selectedId}
        onSelect={handleSelect}
        onToggle={handleToggle}
        disabled={toggle.isPending}
        emptyTitle={feed.data.length === 0 ? "You're all caught up" : "No notifications match"}
        emptyDescription={
          feed.data.length === 0 ? "New notifications will appear here." : "Try a different word, or clear the filters."
        }
      />
    );
  };

  return (
    <WorkspaceContent>
      <Reveal>
        <CollaborationHeader
          title="Notifications"
          description="Everything your workspace and AI employees want you to know — in one place."
        />
      </Reveal>

      <div className="mt-4">
        <NotificationFilterBar />
      </div>

      <div className="relative mt-4 flex min-h-0 gap-4">
        <div className="min-w-0 flex-1">{feedBody()}</div>

        {selectedId ? (
          <>
            <button
              type="button"
              aria-label="Close inspector"
              onClick={() => selectNotification(null)}
              className="fixed inset-0 z-overlay bg-foreground/20 xl:hidden"
            />
            <aside
              aria-label="Notification inspector"
              className={cn(
                "fixed inset-y-0 right-0 z-overlay flex w-96 max-w-[90vw] flex-col overflow-hidden border-l bg-card shadow-lg",
                "xl:static xl:z-auto xl:w-96 xl:shrink-0 xl:rounded-lg xl:border xl:shadow-sm"
              )}
            >
              {detail.data ? (
                <NotificationInspector notification={detail.data} />
              ) : detail.isError ? (
                <ErrorState
                  className="p-6"
                  compact
                  title="Couldn't load this notification"
                  onRetry={() => void detail.refetch()}
                />
              ) : (
                <InspectorLoading />
              )}
            </aside>
          </>
        ) : (
          <aside className="hidden w-96 shrink-0 xl:block">
            <div className="flex h-full items-center justify-center rounded-lg border bg-card p-6 shadow-sm">
              <EmptyState
                icon={MousePointerSquareDashed}
                title="Nothing selected"
                description="Pick a notification to see its details, related records, and history."
              />
            </div>
          </aside>
        )}
      </div>
    </WorkspaceContent>
  );
}
