"use client";

import { memo } from "react";
import { ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { CAPABILITY_LABEL } from "@/types/domain";
import { WidgetShell } from "../components/widget-shell";
import { EntityList } from "../components/entity-list";
import { useRecentTasks } from "../hooks/use-dashboard";

/** Recent Tasks — ordered by the service's sequence, newest first. */
export const RecentTasksWidget = memo(function RecentTasksWidget() {
  const query = useRecentTasks();
  const tasks = query.data ?? [];

  return (
    <WidgetShell
      title="Recent tasks"
      description="What you've delegated most recently."
      href="/workspace/tasks"
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={tasks.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      empty={
        <EmptyState
          compact
          icon={ListChecks}
          title="No tasks yet"
          description="Delegate work and it shows up here."
          action={
            <Button variant="outline" size="sm" href="/workspace/tasks">
              Delegate a task
            </Button>
          }
        />
      }
    >
      <EntityList
        label="Recent tasks"
        items={tasks.map((task) => ({
          id: task.id,
          title: task.title,
          meta: CAPABILITY_LABEL[task.capability],
          icon: ListChecks,
          href: "/workspace/tasks",
          isHighlighted: task.status === "RUNNING",
          trailing: <StatusBadge kind="lifecycle" status={task.status} />,
        }))}
      />
    </WidgetShell>
  );
});
