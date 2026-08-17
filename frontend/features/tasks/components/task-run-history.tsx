"use client";

import { History, RotateCcw } from "lucide-react";
import type { WorkflowRunSummary } from "@/services/workflows";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { useRetryTaskExecution, useTaskExecutions } from "../hooks/use-tasks";

/**
 * Every run this task launched (Sprint 19).
 *
 * The rows are the workflow platform's own history summaries — a task's run
 * *is* a workflow run, recorded by the same engine and read back in the same
 * shape. Each row says how a run went, when, and how long it took; a run that
 * didn't complete offers a retry, which asks the platform to repeat it as a
 * *new* run pointing back at this one. History itself never changes.
 */
export interface TaskRunHistoryProps {
  taskId: string;
  onRetried?: (message: string, tone: "info" | "error") => void;
}

export function TaskRunHistory({ taskId, onRetried }: TaskRunHistoryProps) {
  const query = useTaskExecutions(taskId);
  const retry = useRetryTaskExecution();

  const handleRetry = (run: WorkflowRunSummary) => {
    retry.mutate(
      { id: taskId, executionId: run.id },
      {
        onSuccess: (task) =>
          onRetried?.(
            task.state === "COMPLETED"
              ? "The run was repeated and completed."
              : "The run was repeated and failed again — see the newest entry.",
            "info"
          ),
        onError: (error) =>
          onRetried?.(
            error instanceof Error ? error.message : "That run couldn't be repeated.",
            "error"
          ),
      }
    );
  };

  if (query.isPending) return <LoadingState rows={3} />;

  if (query.isError) {
    return (
      <p className="text-sm text-muted-foreground">
        This task&apos;s run history couldn&apos;t be loaded. Try again in a moment.
      </p>
    );
  }

  const { items, total } = query.data;

  if (items.length === 0) {
    return (
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <History className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        This task hasn&apos;t launched a run yet.
      </p>
    );
  }

  return (
    <div>
      <p className="mb-2 text-xs text-muted-foreground">
        {total} run{total === 1 ? "" : "s"}, newest first
      </p>
      <ol className="-mx-2 space-y-0.5">
        {items.map((run) => (
          <li key={run.id} className="flex items-center gap-3 rounded-md px-2 py-2">
            <StatusBadge kind="lifecycle" status={run.status} className="shrink-0" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm text-foreground" title={formatExactTime(run.startedAt)}>
                {formatRelativeTime(run.startedAt)}
                {run.trigger === "retry" ? " · retry" : null}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {run.completedStepCount} of {run.totalStepCount} step
                {run.totalStepCount === 1 ? "" : "s"} · {formatDuration(run.durationMs)}
                {run.error ? ` · ${run.error}` : null}
              </span>
            </span>
            {run.status !== "COMPLETED" ? (
              <Button
                variant="outline"
                size="sm"
                className="shrink-0"
                disabled={retry.isPending}
                onClick={() => handleRetry(run)}
              >
                <RotateCcw className="size-3.5" aria-hidden="true" />
                Retry
              </Button>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

// --- Formatting -----------------------------------------------------------
//
// Local on purpose: the workflow feature has its own run formatting, and
// features don't import from each other's models — only from services and the
// shared workspace shell.

function formatDuration(durationMs: number | null): string {
  if (durationMs === null || durationMs < 0) return "—";
  if (durationMs < 1000) return `${durationMs} ms`;
  const seconds = durationMs / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds % 60)} s`;
}

function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return "—";
  const elapsedMs = now.getTime() - parsed;
  if (elapsedMs < 60_000) return "Just now";
  const minutes = Math.floor(elapsedMs / 60_000);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function formatExactTime(iso: string): string {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return "";
  return new Date(parsed).toLocaleString();
}
