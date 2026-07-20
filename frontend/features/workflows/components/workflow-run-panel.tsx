"use client";

import { CircleCheck, CircleX, RotateCcw } from "lucide-react";
import type { WorkflowGraph, WorkflowRunDetail, WorkflowRunStep } from "@/services/workflows";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { Spinner } from "@/components/ui/spinner";
import { StatusBadge } from "@/components/ui/status-badge";
import { Panel } from "@/features/workspace/panels/panel";
import { NODE_TYPES } from "../models/node-types";
import { formatDuration, formatExactTime, formatRelativeTime } from "../models/run-format";
import { workflowRunError, workflowRunSummary } from "../models/workflow-messages";
import { cn } from "@/lib/utils";

export interface WorkflowRunPanelProps {
  /** The authored graph, so a step can be named the way the page names it. */
  graph: WorkflowGraph;
  /** The run on display, or `null` when none is selected or one is loading. */
  run: WorkflowRunDetail | null;
  isRunning: boolean;
  isLoading?: boolean;
  /** Offered on a run that failed. Omit where repeating isn't possible. */
  onRetry?: (executionId: string) => void;
  isRetrying?: boolean;
  disabled?: boolean;
}

/**
 * One run in full: how it went, what each step did, and what the platform said.
 *
 * Since Sprint 18.10 this renders a *recorded* run rather than the answer to a
 * request. That is the same component doing less work, not more: a run that has
 * just finished is simply the newest record, so live and historical runs take
 * one path through here and there is no second rendering of the same thing to
 * keep in step.
 *
 * The platform decides everything shown; this reads its answer. Steps come back
 * identified by the node that produced them, so each row is joined to the
 * authored graph and labelled the way the Steps panel labels it — a run and the
 * workflow it ran should not name the same step two ways.
 */
export function WorkflowRunPanel({
  graph,
  run,
  isRunning,
  isLoading = false,
  onRetry,
  isRetrying = false,
  disabled = false,
}: WorkflowRunPanelProps) {
  const failedStepName = run?.failedStepId ? stepLabel(graph, run.failedStepId) : null;
  // A step can stop a run before it produces a record of its own — resolving its
  // inputs is the step's first act and can fail on its own. Then the id is all
  // there is, so the outcome has to name it.
  const isFailureUnrecorded = Boolean(
    run?.failedStepId && !run.steps.some((step) => step.id === run.failedStepId)
  );
  const hasFailed = run?.status === "FAILED";

  return (
    <Panel
      title="Run"
      description={
        run ? (
          <span title={formatExactTime(run.startedAt)}>
            {formatRelativeTime(run.startedAt)} · {formatDuration(run.durationMs)}
            {run.trigger === "retry" ? " · retry" : null}
          </span>
        ) : (
          "Reported by the platform that ran it."
        )
      }
      actions={
        run && hasFailed && onRetry ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onRetry(run.id)}
            disabled={disabled || isRetrying}
            aria-busy={isRetrying}
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            {isRetrying ? "Running…" : "Run again"}
          </Button>
        ) : null
      }
    >
      {isRunning ? (
        <Alert variant="info">
          <span className="flex items-center gap-2">
            <Spinner />
            Running this workflow. Its steps run one after another, so this can take a moment.
          </span>
        </Alert>
      ) : isLoading ? (
        <LoadingState rows={3} />
      ) : run ? (
        <>
          <Alert
            variant={run.status === "COMPLETED" ? "success" : "error"}
            icon={run.status === "COMPLETED" ? CircleCheck : CircleX}
          >
            <p className="font-medium">{workflowRunSummary(run)}</p>
            {run.status !== "COMPLETED" ? (
              <p className="mt-1">
                {isFailureUnrecorded && failedStepName ? `Stopped at ${failedStepName}. ` : null}
                {workflowRunError(run)}
              </p>
            ) : null}
          </Alert>

          {run.steps.length > 0 ? (
            <ol className="mt-4 space-y-2">
              {run.steps.map((step) => (
                <RunStepRow key={step.id} graph={graph} step={step} />
              ))}
            </ol>
          ) : null}

          {run.logs.length > 0 ? <RunLog run={run} /> : null}
        </>
      ) : null}
    </Panel>
  );
}

/** The step's authored name, falling back to the id the platform sent. */
function stepLabel(graph: WorkflowGraph, stepId: string): string {
  const node = graph.nodes.find((candidate) => candidate.id === stepId);
  return node?.name?.trim() || stepId;
}

function RunStepRow({ graph, step }: { graph: WorkflowGraph; step: WorkflowRunStep }) {
  const node = graph.nodes.find((candidate) => candidate.id === step.id);
  const meta = node ? NODE_TYPES[node.kind] : null;
  const Icon = meta?.icon;

  return (
    <li className="rounded-md border p-3">
      <div className="flex items-start justify-between gap-3">
        <span className="flex min-w-0 items-center gap-3">
          {Icon ? (
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
              <Icon className="size-4" aria-hidden="true" />
            </span>
          ) : null}
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">
              {stepLabel(graph, step.id)}
            </span>
            {/* The authored kind when we can resolve it, so a step reads the same
                here as it does everywhere else; the platform's capability name
                only when the node is gone from the graph. */}
            <span className="block truncate text-xs text-muted-foreground">
              {meta ? meta.label : step.capability}
              {step.durationMs !== null ? ` · ${formatDuration(step.durationMs)}` : null}
            </span>
          </span>
        </span>
        <StatusBadge kind="node" status={step.status} className="shrink-0" />
      </div>

      {step.outputs.length > 0 ? (
        <dl className="mt-3 space-y-1.5 border-t pt-3">
          {step.outputs.map((output) => (
            <div key={output.key} className="flex gap-3 text-xs">
              <dt className="w-28 shrink-0 truncate text-muted-foreground">{output.key}</dt>
              <dd className="min-w-0 flex-1 break-words font-mono text-foreground line-clamp-3">
                {output.value}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </li>
  );
}

/**
 * The platform's account of the run.
 *
 * Structured records, not a wall of text: each carries a level and the step it
 * concerns, so the level is what colours it and nothing has to be parsed out of
 * a sentence.
 */
function RunLog({ run }: { run: WorkflowRunDetail }) {
  return (
    <details className="mt-4 rounded-md border">
      <summary className="cursor-pointer rounded-md px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        Log ({run.logs.length})
      </summary>
      <ul className="space-y-1 border-t px-3 py-2">
        {run.logs.map((entry) => (
          <li key={entry.sequence} className="flex gap-2 text-xs">
            <span
              className={cn(
                "w-14 shrink-0 font-medium uppercase tracking-wide",
                entry.level === "error"
                  ? "text-destructive"
                  : entry.level === "warning"
                    ? "text-warning"
                    : "text-muted-foreground"
              )}
            >
              {entry.level}
            </span>
            <span className="min-w-0 flex-1 break-words text-foreground">{entry.message}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
