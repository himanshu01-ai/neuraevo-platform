"use client";

import { History } from "lucide-react";
import type { WorkflowRunSummary } from "@/services/workflows";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { Panel } from "@/features/workspace/panels/panel";
import { formatDuration, formatExactTime, formatRelativeTime } from "../models/run-format";
import { cn } from "@/lib/utils";

export interface WorkflowRunHistoryProps {
  runs: WorkflowRunSummary[];
  total: number;
  isLoading: boolean;
  isError: boolean;
  /** The run currently on display, so the list can show which one that is. */
  selectedId: string | null;
  onSelect: (executionId: string) => void;
}

/**
 * Every time this workflow has run (Sprint 18.10).
 *
 * A list of outcomes rather than a list of events: each row says how a run went,
 * when, and how long it took, which is what makes two runs comparable at a
 * glance. Selecting one shows it in full beside this.
 *
 * Summaries only, by design — the platform's history endpoint returns no steps
 * or logs for a list, so this renders what a list needs and nothing it doesn't.
 */
export function WorkflowRunHistory({
  runs,
  total,
  isLoading,
  isError,
  selectedId,
  onSelect,
}: WorkflowRunHistoryProps) {
  return (
    <Panel
      title="History"
      description={total > 0 ? `${total} run${total === 1 ? "" : "s"}` : undefined}
    >
      {isLoading ? (
        <LoadingState rows={3} />
      ) : isError ? (
        <p className="text-sm text-muted-foreground">
          This workflow&apos;s history couldn&apos;t be loaded. Try again in a moment.
        </p>
      ) : runs.length === 0 ? (
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <History className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          This workflow hasn&apos;t been run yet.
        </p>
      ) : (
        <ol className="-mx-2 space-y-0.5">
          {runs.map((run) => {
            const isSelected = run.id === selectedId;
            return (
              <li key={run.id}>
                <button
                  type="button"
                  onClick={() => onSelect(run.id)}
                  aria-current={isSelected ? "true" : undefined}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-md px-2 py-2 text-left transition-colors",
                    "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isSelected && "bg-accent"
                  )}
                >
                  <StatusBadge kind="lifecycle" status={run.status} className="shrink-0" />
                  <span className="min-w-0 flex-1">
                    <span
                      className="block truncate text-sm text-foreground"
                      title={formatExactTime(run.startedAt)}
                    >
                      {formatRelativeTime(run.startedAt)}
                      {run.trigger === "retry" ? " · retry" : null}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {run.completedStepCount} of {run.totalStepCount} step
                      {run.totalStepCount === 1 ? "" : "s"} · {formatDuration(run.durationMs)}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
