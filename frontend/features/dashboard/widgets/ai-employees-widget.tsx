"use client";

import { memo } from "react";
import { Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { WidgetShell } from "../components/widget-shell";
import { EntityList } from "../components/entity-list";
import { useActiveEmployees } from "../hooks/use-dashboard";

/** Active AI Employees — who is on your roster and what they're doing. */
export const AIEmployeesWidget = memo(function AIEmployeesWidget() {
  const query = useActiveEmployees();
  const employees = query.data ?? [];

  return (
    <WidgetShell
      title="Active AI employees"
      description="Your roster and what each one is doing."
      href="/workspace/ai-employees"
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={employees.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      empty={
        <EmptyState
          compact
          icon={Bot}
          title="No AI employees yet"
          description="Create one to start delegating work."
          action={
            <Button variant="outline" size="sm" href="/workspace/ai-employees">
              Browse AI employees
            </Button>
          }
        />
      }
    >
      <EntityList
        label="Active AI employees"
        items={employees.map((employee) => ({
          id: employee.id,
          title: employee.name,
          meta: `${employee.role} · ${employee.activeTasks === 1 ? "1 active task" : `${employee.activeTasks} active tasks`}`,
          icon: Bot,
          href: "/workspace/ai-employees",
          isHighlighted: employee.status === "RUNNING",
          trailing: <StatusBadge kind="lifecycle" status={employee.status} />,
        }))}
      />
    </WidgetShell>
  );
});
