"use client";

import Link from "next/link";
import { ListOrdered } from "lucide-react";
import { TASK_EXECUTION_MODE_LABEL } from "@/services/tasks";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { useTaskQueue } from "../hooks/use-tasks";
import { cn } from "@/lib/utils";

export interface QueueManagerProps {
  /** Trims the list where space is tight (the directory column). */
  limit?: number;
  className?: string;
}

/**
 * The line, in the order the platform put it.
 *
 * Read-only, and deliberately so: ordering is the scheduler's judgement, not the
 * UI's. Nothing here reorders, promotes or starts anything — position and
 * estimated order are carried straight through, and the queue is changed by
 * changing a task (its priority, or whether it's queued at all).
 */
export function QueueManager({ limit, className }: QueueManagerProps) {
  const query = useTaskQueue();

  if (query.isPending) return <LoadingState rows={3} className={className} />;

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load the queue"
        description="What's waiting couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  const { entries, waitingCount } = query.data;
  const shown = limit ? entries.slice(0, limit) : entries;

  if (entries.length === 0) {
    return (
      <EmptyState
        compact
        icon={ListOrdered}
        title="Nothing waiting"
        description="Queued tasks line up here in the order they'll run."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-sm text-muted-foreground">
        <span className="font-medium tabular-nums text-foreground">{waitingCount}</span>{" "}
        {waitingCount === 1 ? "task is" : "tasks are"} waiting.
      </p>

      <ol className="space-y-2">
        {shown.map((entry) => (
          <li key={entry.taskId} className="rounded-md border bg-card p-3 shadow-sm">
            <div className="flex items-start gap-3">
              <span
                aria-hidden="true"
                className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular-nums text-muted-foreground"
              >
                {entry.position}
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-mono text-[0.6875rem] text-muted-foreground">{entry.businessId}</p>
                    <h4 className="truncate text-sm font-medium">
                      <Link
                        href={`/workspace/tasks/${entry.taskId}`}
                        className="rounded-sm text-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <span className="sr-only">Position {entry.position}: </span>
                        {entry.taskName}
                      </Link>
                    </h4>
                  </div>
                  <Badge variant={TONE_VARIANT[PRIORITY_TONE[entry.priority]]} className="shrink-0">
                    {PRIORITY_LABEL[entry.priority]}
                  </Badge>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Avatar name={entry.employeeName} className="size-4 text-[0.5rem]" />
                    {entry.employeeName}
                  </span>
                  <span>{TASK_EXECUTION_MODE_LABEL[entry.executionMode]}</span>
                  <span className="text-foreground">{entry.estimatedOrder}</span>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>

      {limit && entries.length > limit ? (
        <p className="text-xs text-muted-foreground">
          <Link
            href="/workspace/tasks/queue"
            className="rounded-sm text-primary transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {entries.length - limit} more in the queue
          </Link>
        </p>
      ) : null}
    </div>
  );
}
