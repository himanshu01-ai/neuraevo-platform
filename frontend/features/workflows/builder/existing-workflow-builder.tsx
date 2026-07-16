"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { useBuilderStore } from "@/store/workflow";
import { useWorkflowDetail } from "../hooks/use-workflows";
import { WorkflowLoadingState } from "../components/workflow-loading-state";
import { WorkflowBuilder } from "./workflow-builder";

/**
 * The builder for a saved workflow: load it, copy it into the draft once, edit.
 *
 * The builder only renders once the draft actually belongs to this id —
 * otherwise the frame between "data arrived" and "hydrate ran" would flash the
 * previous workflow's graph.
 */
export function ExistingWorkflowBuilder({ id }: { id: string }) {
  const query = useWorkflowDetail(id);
  const hydrate = useBuilderStore((s) => s.hydrate);
  const workflowId = useBuilderStore((s) => s.workflowId);

  useEffect(() => {
    if (query.data) hydrate(query.data);
  }, [query.data, hydrate]);

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

  if (query.isPending || workflowId !== id) return <WorkflowLoadingState />;

  return <WorkflowBuilder />;
}
