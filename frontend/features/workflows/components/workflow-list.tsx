"use client";

import { useMemo, useState } from "react";
import { LayoutTemplate, Plus, Search } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useWorkflowActions } from "../hooks/use-workflow-actions";
import { useWorkflowList } from "../hooks/use-workflows";
import { WorkflowCard } from "./workflow-card";
import { WorkflowEmptyState } from "./workflow-empty-state";
import { WorkflowCardGridLoading } from "./workflow-loading-state";
import { WorkflowHeader } from "./workflow-header";

/** The workflow list screen. */
export function WorkflowList() {
  const query = useWorkflowList();
  const actions = useWorkflowActions();
  const [search, setSearch] = useState("");

  const workflows = useMemo(() => {
    const rows = query.data ?? [];
    const term = search.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter(
      (w) => w.name.toLowerCase().includes(term) || w.description.toLowerCase().includes(term)
    );
  }, [query.data, search]);

  const body = () => {
    if (query.isError) {
      return (
        <ErrorState
          title="Couldn't load workflows"
          description="Your workflows couldn't be loaded. Try again in a moment."
          onRetry={() => void query.refetch()}
        />
      );
    }

    if (query.isPending) return <WorkflowCardGridLoading />;

    if ((query.data?.length ?? 0) === 0) {
      return (
        <div className="rounded-lg border bg-card shadow-sm">
          <WorkflowEmptyState />
        </div>
      );
    }

    if (workflows.length === 0) {
      return (
        <div className="rounded-lg border bg-card shadow-sm">
          <WorkflowEmptyState
            title="No workflows match"
            description="Try a different word."
            showActions={false}
          />
        </div>
      );
    }

    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {workflows.map((workflow) => (
          <WorkflowCard
            key={workflow.id}
            workflow={workflow}
            onDuplicate={actions.duplicate}
            onPublish={actions.publish}
            onUnpublish={actions.unpublish}
            onArchive={actions.archive}
            onRestore={actions.restore}
            onDelete={actions.remove}
            isBusy={actions.isBusy}
          />
        ))}
      </div>
    );
  };

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkflowHeader
          title="Workflows"
          description="Build the work you repeat, then let your AI employee run it."
          actions={
            <>
              <Button variant="outline" href="/workspace/workflows/templates">
                <LayoutTemplate className="size-4" aria-hidden="true" />
                Templates
              </Button>
              <Button href="/workspace/workflows/new">
                <Plus className="size-4" aria-hidden="true" />
                New workflow
              </Button>
            </>
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

      <div className="relative mt-6 max-w-sm">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search workflows"
          aria-label="Search workflows"
          className="pl-9"
        />
      </div>

      <div className="mt-6">{body()}</div>
    </WorkspaceContent>
  );
}
