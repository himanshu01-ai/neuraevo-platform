"use client";

import { Hourglass } from "lucide-react";
import type { TaskDetail } from "@/services/tasks";
import { EmptyState } from "@/components/ui/empty-state";
import { useTaskArtifacts } from "../hooks/use-tasks";
import { ARTIFACT_META } from "../models/artifact-kinds";
import { cn } from "@/lib/utils";

export interface ResultsPanelProps {
  task: TaskDetail;
  className?: string;
}

/**
 * What a finished run produced.
 *
 * A result exists only once a task reaches a terminal state — a summary of a run
 * still in flight would be a guess, so this says "not yet" rather than
 * half-reporting. A failed run has a result too: what it got to, and where it
 * stopped, is exactly what you need when something breaks.
 */
export function ResultsPanel({ task, className }: ResultsPanelProps) {
  const artifacts = useTaskArtifacts(task.result ? task.id : null);

  if (!task.result) {
    return (
      <EmptyState
        compact
        icon={Hourglass}
        title="No result yet"
        description="This task hasn't finished, so there's nothing to report."
        className={className}
      />
    );
  }

  const result = task.result;
  const generated = (artifacts.data ?? []).filter((a) => result.generatedArtifactIds.includes(a.id));

  return (
    <div className={cn("space-y-5", className)}>
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Summary</h4>
        <p className="mt-1.5 text-sm leading-relaxed text-foreground">{result.summary}</p>
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Execution report
        </h4>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{result.executionReport}</p>
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Workflow outcome
        </h4>
        <p className="mt-1.5 text-sm text-muted-foreground">{result.workflowOutcome}</p>
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Capability summary
        </h4>
        {result.capabilitySummary.length === 0 ? (
          <p className="mt-1.5 text-sm text-muted-foreground">No capabilities were reached for.</p>
        ) : (
          <ul className="mt-1.5 space-y-2">
            {result.capabilitySummary.map((entry) => (
              <li key={entry.capability} className="rounded-md border bg-background p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-foreground">{entry.capability}</span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                    {entry.invocations} {entry.invocations === 1 ? "call" : "calls"}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{entry.outcome}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Generated artifacts
        </h4>
        {generated.length === 0 ? (
          <p className="mt-1.5 text-sm text-muted-foreground">Nothing was produced.</p>
        ) : (
          <ul className="mt-1.5 space-y-1">
            {generated.map((artifact) => {
              const Icon = ARTIFACT_META[artifact.kind].icon;
              return (
                <li key={artifact.id} className="flex items-center gap-2 text-sm">
                  <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="min-w-0 truncate font-mono text-xs text-foreground">{artifact.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{artifact.size}</span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Completion details
        </h4>
        <dl className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {result.completionDetails.map((detail) => (
            <div key={detail.label} className="rounded-md border bg-background p-2.5">
              <dt className="text-xs text-muted-foreground">{detail.label}</dt>
              <dd className="mt-0.5 text-sm font-medium text-foreground">{detail.value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
