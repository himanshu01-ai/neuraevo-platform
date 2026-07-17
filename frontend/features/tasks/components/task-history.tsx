"use client";

import { useMemo } from "react";
import Link from "next/link";
import { History } from "lucide-react";
import { TASK_EXECUTION_MODE_LABEL, isTerminal } from "@/services/tasks";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Progress } from "@/components/ui/progress";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { useTaskList } from "../hooks/use-tasks";
import { TaskListLoading } from "./task-loading-state";
import { TaskStateBadge } from "./task-state-badge";

/**
 * Everything that's finished: completed, failed, or cancelled.
 *
 * "Finished" is `TERMINAL_TASK_STATES` from `services/tasks` rather than a list
 * spelled out here, so history and the toolbar's command rules always agree
 * about which tasks have stopped for good.
 */
export function TaskHistory() {
  const query = useTaskList();

  const finished = useMemo(() => (query.data ?? []).filter((task) => isTerminal(task.state)), [query.data]);

  if (query.isPending) return <TaskListLoading count={4} />;

  if (query.isError) {
    return (
      <ErrorState
        title="Couldn't load history"
        description="What's finished couldn't be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }

  if (finished.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="Nothing finished yet"
        description="Tasks that complete, fail, or get cancelled are kept here."
      />
    );
  }

  return (
    <ul className="space-y-2">
      {finished.map((task) => (
        <li key={task.id} className="rounded-lg border bg-card p-4 shadow-sm transition-colors hover:border-primary/30">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-mono text-xs text-muted-foreground">{task.businessId}</p>
              <h3 className="mt-0.5 truncate text-sm font-semibold">
                <Link
                  href={`/workspace/tasks/${task.id}`}
                  className="rounded-sm text-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {task.name}
                </Link>
              </h3>
              <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{task.description}</p>
            </div>
            <TaskStateBadge state={task.state} />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
            <Badge variant={TONE_VARIANT[PRIORITY_TONE[task.priority]]}>{PRIORITY_LABEL[task.priority]}</Badge>
            <Badge variant="outline">{TASK_EXECUTION_MODE_LABEL[task.executionMode]}</Badge>
            <span>{task.workflow ? task.workflow.workflowName : "No workflow"}</span>
            {task.assignee ? (
              <span className="flex items-center gap-1.5">
                <Avatar name={task.assignee.employeeName} className="size-4 text-[0.5rem]" />
                {task.assignee.employeeName}
              </span>
            ) : null}
          </div>

          <div className="mt-2 flex items-center gap-2">
            <Progress value={task.progress} label={`${task.name} progress at finish`} className="h-1 flex-1" />
            <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
              {task.progress}% at finish
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
