import { ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export interface TaskEmptyStateProps {
  title?: string;
  description?: string;
  compact?: boolean;
  /** Hides the action where it'd be redundant. */
  showActions?: boolean;
  className?: string;
}

/**
 * The task domain's empty state: <EmptyState> with the task icon and the one way
 * out — describe the work you want done.
 */
export function TaskEmptyState({
  title = "No tasks yet",
  description = "Describe a piece of work, assign a workflow and an employee, and queue it.",
  compact,
  showActions = true,
  className,
}: TaskEmptyStateProps) {
  return (
    <EmptyState
      compact={compact}
      className={className}
      icon={ListChecks}
      title={title}
      description={description}
      action={
        showActions ? (
          <Button size="sm" href="/workspace/tasks/new">
            Create task
          </Button>
        ) : null
      }
    />
  );
}
