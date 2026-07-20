"use client";

import { CircleCheck, CircleX } from "lucide-react";
import type { WorkflowGraph, WorkflowRun, WorkflowRunStep } from "@/services/workflows";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { StatusBadge } from "@/components/ui/status-badge";
import { Panel } from "@/features/workspace/panels/panel";
import { NODE_TYPES } from "../models/node-types";
import { workflowRunError, workflowRunSummary } from "../models/workflow-messages";

export interface WorkflowRunPanelProps {
  /** The authored graph, so a step can be named the way the page names it. */
  graph: WorkflowGraph;
  /** The last finished run, or `null` if none has finished yet. */
  run: WorkflowRun | null;
  isRunning: boolean;
}

/**
 * What happened the last time this workflow ran.
 *
 * The platform decides everything shown here; this reads its answer. Steps come
 * back identified by the node that produced them, so each row is joined to the
 * authored graph and labelled the same way the Steps panel above labels it —
 * a run and the workflow it ran should not name the same step two ways.
 *
 * The run's outcome is announced by the `Alert` it lives in (`role="status"`,
 * `role="alert"` when it failed), which is how every other outcome in this
 * product announces itself.
 */
export function WorkflowRunPanel({ graph, run, isRunning }: WorkflowRunPanelProps) {
  const failedStepName = run?.failedStepId ? stepLabel(graph, run.failedStepId) : null;
  // A step can stop a run before it produces a record of its own — resolving its
  // inputs is the step's first act and can fail on its own. Then the id is all
  // there is, so the outcome has to name it.
  const isFailureUnrecorded = Boolean(
    run?.failedStepId && !run.steps.some((step) => step.id === run.failedStepId)
  );

  return (
    <Panel
      title="Last run"
      description="Reported by the platform that ran it."
    >
      {isRunning ? (
        <Alert variant="info">
          <span className="flex items-center gap-2">
            <Spinner />
            Running this workflow. Its steps run one after another, so this can take a moment.
          </span>
        </Alert>
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
