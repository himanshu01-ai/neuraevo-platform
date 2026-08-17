"use client";

import { memo } from "react";
import { Bell } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { WidgetShell } from "../components/widget-shell";
import { EntityList } from "../components/entity-list";
import { useRecentNotifications } from "../hooks/use-dashboard";

/** Notifications Preview — the most recent few; the full list lives elsewhere. */
export const NotificationWidget = memo(function NotificationWidget() {
  const query = useRecentNotifications();
  const notifications = query.data ?? [];

  return (
    <WidgetShell
      title="Notifications"
      description="The latest from your workspace."
      href="/workspace/notifications"
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={notifications.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      empty={<EmptyState compact icon={Bell} title="No notifications" description="You're all caught up." />}
    >
      <EntityList
        label="Recent notifications"
        items={notifications.map((notification) => ({
          id: notification.id,
          title: notification.title,
          meta: notification.detail,
          icon: Bell,
          href: "/workspace/notifications",
          isHighlighted: !notification.isRead,
          trailing: (
            <Badge variant={TONE_VARIANT[PRIORITY_TONE[notification.priority]]}>
              {PRIORITY_LABEL[notification.priority]}
            </Badge>
          ),
        }))}
      />
    </WidgetShell>
  );
});
