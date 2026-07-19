"use client";

import { useEffect } from "react";
import { Archive } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { useBuilderStore } from "@/store/workflow";
import { useWorkflowActions } from "../hooks/use-workflow-actions";
import { useWorkflowDetail } from "../hooks/use-workflows";
import { WorkflowLoadingState } from "../components/workflow-loading-state";
import { WorkflowBuilder } from "./workflow-builder";

/**
 * The builder for a saved workflow: load it, copy it into the draft once, edit.
 *
 * The builder only renders once the draft actually belongs to this id —
 * otherwise the frame between "data arrived" and "hydrate ran" would flash the
 * previous workflow's graph.
 *
 * An archived workflow never reaches the editable builder. Editing one would be
 * rejected by the backend (409) and would let a retired workflow drift from
 * what was archived, so it's gated behind a read-only notice that offers
 * restore. Restoring flips its lifecycle in the cache and the builder mounts.
 */
export function ExistingWorkflowBuilder({ id }: { id: string }) {
  const query = useWorkflowDetail(id);
  const hydrate = useBuilderStore((s) => s.hydrate);
  const workflowId = useBuilderStore((s) => s.workflowId);
  const isArchived = query.data?.lifecycle === "ARCHIVED";

  useEffect(() => {
    // Don't seed the editor from an archived workflow — it isn't editable, and
    // hydrating would arm the toolbar's Save against a workflow the backend
    // would refuse.
    if (query.data && !isArchived) hydrate(query.data);
  }, [query.data, isArchived, hydrate]);

  if (query.isError) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <ErrorState
          title="Workflow not found"
          description="This workflow doesn't exist, or it was deleted."
          action={
            <Button variant="outline" href="/workspace/workflows">
              Back to workflows
            </Button>
          }
        />
      </div>
    );
  }

  if (query.isPending) return <WorkflowLoadingState />;

  if (isArchived && query.data) return <ArchivedGate id={id} name={query.data.name} />;

  if (workflowId !== id) return <WorkflowLoadingState />;

  return <WorkflowBuilder />;
}

/** Read-only stop for an archived workflow, with the one move that unblocks it. */
function ArchivedGate({ id, name }: { id: string; name: string }) {
  const actions = useWorkflowActions();

  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="w-full max-w-md text-center" role="status">
        <span className="mx-auto inline-flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Archive className="size-6" aria-hidden="true" />
        </span>
        <h2 className="mt-3 text-sm font-semibold text-foreground">This workflow is archived</h2>
        <p className="mx-auto mt-1 max-w-xs text-sm text-muted-foreground">
          Archived workflows can&apos;t be edited. Restore “{name}” to make changes — its steps
          stay exactly as they were.
        </p>

        {actions.feedback?.tone === "error" ? (
          <Alert variant="error" className="mt-4 text-left">
            {actions.feedback.message}
          </Alert>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Button onClick={() => actions.restore({ id, name })} disabled={actions.isBusy}>
            {actions.pending === "restore" ? "Restoring…" : "Restore workflow"}
          </Button>
          <Button variant="outline" href={`/workspace/workflows/${id}`}>
            View details
          </Button>
        </div>
      </div>
    </div>
  );
}
