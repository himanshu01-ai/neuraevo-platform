"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Archive,
  ArchiveRestore,
  CircleCheck,
  Copy,
  Pencil,
  Play,
  Send,
  Settings,
  TriangleAlert,
  Undo2,
} from "lucide-react";
import { dependenciesOf } from "@/services/workflows";
import { EXECUTION_MODE_LABEL } from "@/types/domain";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { NODE_TYPES } from "../models/node-types";
import { validateWorkflow } from "../validation/rules";
import { useWorkflowActions } from "../hooks/use-workflow-actions";
import {
  useWorkflowDetail,
  useWorkflowExecution,
  useWorkflowExecutions,
} from "../hooks/use-workflows";
import { WorkflowCardGridLoading } from "./workflow-loading-state";
import { WorkflowEmptyState } from "./workflow-empty-state";
import { WorkflowHeader } from "./workflow-header";
import { WorkflowRunHistory } from "./workflow-run-history";
import { WorkflowRunPanel } from "./workflow-run-panel";
import { cn } from "@/lib/utils";

/**
 * A workflow at rest: what it contains, how it's wired, what validation says,
 * and every lifecycle move — without opening the builder. Read-only for the
 * structure; the lifecycle actions live here because this is the one workflow
 * screen that shows a single workflow whole.
 *
 * Since Sprint 18.7 it is also where a published workflow is run. Running lives
 * here for the same reason: a run's result is a list of steps, and this is the
 * only screen with the graph in hand to name them.
 */
export function WorkflowDetails({ id }: { id: string }) {
  const router = useRouter();
  const query = useWorkflowDetail(id);
  const detail = query.data;

  // Which run is on display. The only state this screen owns: everything about
  // the run itself is fetched by id, so there is one copy of it and selecting a
  // different one is a different query rather than a second store to keep in
  // step. `null` means "the most recent, if there is one".
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Duplicating makes a new workflow, so go to it; every other action stays
  // here and reports what changed.
  const actions = useWorkflowActions({
    onDuplicated: (clone) => router.push(`/workspace/workflows/${clone.id}`),
    // A run that just finished is the newest record, so it is shown the same
    // way any other is — by selecting it.
    onRan: (run) => setSelectedRunId(run.executionId),
  });

  const historyQuery = useWorkflowExecutions(id);
  const runs = historyQuery.data?.items ?? [];
  // Falling back to the newest run means the panel has something to show the
  // moment the page opens, without the screen tracking which that is.
  const displayedRunId = selectedRunId ?? runs[0]?.id ?? null;
  const runQuery = useWorkflowExecution(displayedRunId);

  const report = useMemo(() => (detail ? validateWorkflow(detail.graph) : null), [detail]);

  if (query.isPending) {
    return (
      <WorkspaceContent>
        <WorkflowCardGridLoading count={3} />
      </WorkspaceContent>
    );
  }

  if (query.isError || !detail) {
    return (
      <WorkspaceContent>
        <ErrorState
          title="Workflow not found"
          description="This workflow doesn't exist, or it was deleted."
          action={
            <Button variant="outline" href="/workspace/workflows">
              Back to workflows
            </Button>
          }
        />
      </WorkspaceContent>
    );
  }

  const isArchived = detail.lifecycle === "ARCHIVED";
  const isPublished = detail.lifecycle === "PUBLISHED";
  const ref = { id: detail.id, name: detail.name };

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkflowHeader
          title={detail.name}
          description={detail.description}
          lifecycle={detail.lifecycle}
          actions={
            isArchived ? (
              // Archived: viewable, but not editable. The only forward move is
              // to restore it, so that's the primary action.
              <>
                <Button variant="outline" onClick={() => actions.duplicate(ref)} disabled={actions.isBusy}>
                  <Copy className="size-4" aria-hidden="true" />
                  {actions.pending === "duplicate" ? "Duplicating…" : "Duplicate"}
                </Button>
                <Button onClick={() => actions.restore(ref)} disabled={actions.isBusy}>
                  <ArchiveRestore className="size-4" aria-hidden="true" />
                  {actions.pending === "restore" ? "Restoring…" : "Restore"}
                </Button>
              </>
            ) : (
              <>
                {/* Running is offered for a published workflow and nowhere else.
                    A draft isn't released yet and an archived one is retired —
                    the platform refuses both, and the UI shouldn't invite a
                    click it knows will be turned down. */}
                {isPublished ? (
                  <Button
                    onClick={() => actions.run(ref)}
                    disabled={actions.isBusy}
                    aria-busy={actions.pending === "run"}
                  >
                    <Play className="size-4" aria-hidden="true" />
                    {actions.pending === "run" ? "Running…" : "Run"}
                  </Button>
                ) : null}
                <Button
                  variant="outline"
                  onClick={() => actions.archive(ref)}
                  disabled={actions.isBusy}
                >
                  <Archive className="size-4" aria-hidden="true" />
                  {actions.pending === "archive" ? "Archiving…" : "Archive"}
                </Button>
                {isPublished ? (
                  <Button
                    variant="outline"
                    onClick={() => actions.unpublish(ref)}
                    disabled={actions.isBusy}
                  >
                    <Undo2 className="size-4" aria-hidden="true" />
                    {actions.pending === "unpublish" ? "Working…" : "Move to draft"}
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    onClick={() => actions.publish(ref)}
                    disabled={actions.isBusy}
                  >
                    <Send className="size-4" aria-hidden="true" />
                    {actions.pending === "publish" ? "Publishing…" : "Publish"}
                  </Button>
                )}
                <Button variant="outline" href={`/workspace/workflows/${detail.id}/settings`}>
                  <Settings className="size-4" aria-hidden="true" />
                  Settings
                </Button>
                {/* Editing leads for a draft; once published, running does. */}
                <Button
                  variant={isPublished ? "outline" : "primary"}
                  href={`/workspace/workflows/${detail.id}/builder`}
                >
                  <Pencil className="size-4" aria-hidden="true" />
                  Open in builder
                </Button>
              </>
            )
          }
        />
      </Reveal>

      {actions.feedback ? (
        <Alert
          variant={actions.feedback.tone === "error" ? "error" : "success"}
          className="mt-4"
        >
          {actions.feedback.message}
        </Alert>
      ) : null}

      {isArchived ? (
        <Alert variant="warning" className="mt-4">
          This workflow is archived. Restore it to edit or run it — its structure
          stays exactly as it was.
        </Alert>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          {/* Only once there's something to report — the page reads exactly as
              it did before this workflow was ever run. */}
          {actions.isRunning || displayedRunId ? (
            <WorkflowRunPanel
              graph={detail.graph}
              run={runQuery.data ?? null}
              isRunning={actions.isRunning}
              isLoading={runQuery.isPending && Boolean(displayedRunId)}
              onRetry={actions.retry}
              isRetrying={actions.pending === "retry"}
              disabled={actions.isBusy}
            />
          ) : null}

          <Reveal delay={0.05}>
            <Panel title="Steps" description="In the order the platform would resolve them.">
              {detail.graph.nodes.length === 0 ? (
                <WorkflowEmptyState
                  compact
                  title="No steps"
                  description="Open the builder to add the first one."
                  showActions={false}
                />
              ) : (
                <ol className="-mx-2 space-y-0.5">
                  {detail.graph.nodes.map((node) => {
                    const meta = NODE_TYPES[node.kind];
                    const Icon = meta.icon;
                    const dependencies = dependenciesOf(detail.graph, node.id);
                    return (
                      <li key={node.id} className="flex items-center gap-3 rounded-md px-2 py-2">
                        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                          <Icon className="size-4" aria-hidden="true" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-foreground">{node.name}</span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {meta.label}
                            {dependencies.length > 0
                              ? ` · runs after ${dependencies.length} step${dependencies.length === 1 ? "" : "s"}`
                              : " · starting step"}
                          </span>
                        </span>
                      </li>
                    );
                  })}
                </ol>
              )}
            </Panel>
          </Reveal>
        </div>

        <div className="min-w-0 space-y-6">
          <Reveal delay={0.05}>
            <Panel title="Summary">
              <dl className="space-y-2.5 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-muted-foreground">Steps</dt>
                  <dd className="font-medium text-foreground">{detail.graph.nodes.length}</dd>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-muted-foreground">Connections</dt>
                  <dd className="font-medium text-foreground">{detail.graph.edges.length}</dd>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-muted-foreground">Execution mode</dt>
                  <dd className="font-medium text-foreground">
                    {EXECUTION_MODE_LABEL[detail.settings.executionMode]}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-muted-foreground">Stop on failure</dt>
                  <dd className="font-medium text-foreground">{detail.settings.stopOnFailure ? "Yes" : "No"}</dd>
                </div>
              </dl>
            </Panel>
          </Reveal>

          {/* History sits with the summary rather than beside the steps: it is
              a property of this workflow, like its shape, and the run it selects
              renders in the wider column where step outputs have room. */}
          <Reveal delay={0.075}>
            <WorkflowRunHistory
              runs={runs}
              total={historyQuery.data?.total ?? 0}
              isLoading={historyQuery.isPending}
              isError={historyQuery.isError}
              selectedId={displayedRunId}
              onSelect={setSelectedRunId}
            />
          </Reveal>

          <Reveal delay={0.1}>
            <Panel title="Validation">
              {report && report.issues.length > 0 ? (
                <ul className="space-y-2">
                  {report.issues.map((issue) => (
                    <li key={`${issue.rule}-${issue.message}`} className="flex items-start gap-2 text-sm">
                      <TriangleAlert
                        className={cn(
                          "mt-0.5 size-4 shrink-0",
                          issue.severity === "error" ? "text-destructive" : "text-warning"
                        )}
                        aria-hidden="true"
                      />
                      <span className="min-w-0 text-foreground">{issue.message}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="flex items-start gap-2 text-sm text-muted-foreground">
                  <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
                  Structurally sound. The platform makes the final call on readiness.
                </p>
              )}
            </Panel>
          </Reveal>
        </div>
      </div>
    </WorkspaceContent>
  );
}
