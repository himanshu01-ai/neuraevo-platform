import { Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export interface WorkflowEmptyStateProps {
  title?: string;
  description?: string;
  compact?: boolean;
  /** Hides the actions where they'd be redundant (e.g. over the canvas). */
  showActions?: boolean;
  className?: string;
}

/**
 * The workflow domain's empty state: <EmptyState> with the workflow icon and the
 * two ways out — start blank or start from a template.
 */
export function WorkflowEmptyState({
  title = "No workflows yet",
  description = "Build one from scratch, or start from a template.",
  compact,
  showActions = true,
  className,
}: WorkflowEmptyStateProps) {
  return (
    <EmptyState
      compact={compact}
      className={className}
      icon={Workflow}
      title={title}
      description={description}
      action={
        showActions ? (
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button size="sm" href="/workspace/workflows/new">
              New workflow
            </Button>
            <Button variant="outline" size="sm" href="/workspace/workflows/templates">
              Browse templates
            </Button>
          </div>
        ) : null
      }
    />
  );
}
