"use client";

import { memo } from "react";
import { Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { WidgetShell } from "../components/widget-shell";
import { EntityList } from "../components/entity-list";
import { useRecentWorkflows } from "../hooks/use-dashboard";

/**
 * Recent Workflows. Step counts are read out as "3 of 5 steps" — the service's
 * own counters, stated plainly. No bar, no percentage, nothing derived.
 */
export const WorkflowWidget = memo(function WorkflowWidget() {
  const query = useRecentWorkflows();
  const workflows = query.data ?? [];

  return (
    <WidgetShell
      title="Recent workflows"
      description="The workflows your workspace ran most recently."
      href="/workspace/workflows"
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={workflows.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      empty={
        <EmptyState
          compact
          icon={Workflow}
          title="No workflows yet"
          description="Turn work you repeat into a workflow."
          action={
            <Button variant="outline" size="sm" href="/workspace/workflows">
              Browse workflows
            </Button>
          }
        />
      }
    >
      <EntityList
        label="Recent workflows"
        items={workflows.map((workflow) => ({
          id: workflow.id,
          title: workflow.name,
          meta: `${workflow.completedNodes} of ${workflow.totalNodes} steps`,
          icon: Workflow,
          href: "/workspace/workflows",
          isHighlighted: workflow.status === "RUNNING",
          trailing: <StatusBadge kind="lifecycle" status={workflow.status} />,
        }))}
      />
    </WidgetShell>
  );
});
