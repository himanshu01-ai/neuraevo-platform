"use client";

import { useMemo } from "react";
import { CircleCheck, Pencil, Settings, TriangleAlert } from "lucide-react";
import { dependenciesOf } from "@/services/workflows";
import { EXECUTION_MODE_LABEL } from "@/types/domain";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { NODE_TYPES } from "../models/node-types";
import { validateWorkflow } from "../validation/rules";
import { useWorkflowDetail } from "../hooks/use-workflows";
import { WorkflowCardGridLoading } from "./workflow-loading-state";
import { WorkflowEmptyState } from "./workflow-empty-state";
import { WorkflowHeader } from "./workflow-header";
import { cn } from "@/lib/utils";

/**
 * A workflow at rest: what it contains, how it's wired, and what validation says
 * — without opening the builder. Read-only.
 */
export function WorkflowDetails({ id }: { id: string }) {
  const query = useWorkflowDetail(id);
  const detail = query.data;

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

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkflowHeader
          title={detail.name}
          description={detail.description}
          status={detail.status}
          actions={
            <>
              <Button variant="outline" href={`/workspace/workflows/${detail.id}/settings`}>
                <Settings className="size-4" aria-hidden="true" />
                Settings
              </Button>
              <Button href={`/workspace/workflows/${detail.id}/builder`}>
                <Pencil className="size-4" aria-hidden="true" />
                Open in builder
              </Button>
            </>
          }
        />
      </Reveal>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 lg:col-span-2">
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
