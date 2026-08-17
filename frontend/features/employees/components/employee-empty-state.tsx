import { Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export interface EmployeeEmptyStateProps {
  title?: string;
  description?: string;
  compact?: boolean;
  /** Hides the actions where they'd be redundant (e.g. beside a builder). */
  showActions?: boolean;
  className?: string;
}

/**
 * The employee domain's empty state: <EmptyState> with the employee icon and the
 * two ways out — hire from scratch, or start from a template.
 */
export function EmployeeEmptyState({
  title = "No employees yet",
  description = "Hire one from scratch, or start from a template.",
  compact,
  showActions = true,
  className,
}: EmployeeEmptyStateProps) {
  return (
    <EmptyState
      compact={compact}
      className={className}
      icon={Bot}
      title={title}
      description={description}
      action={
        showActions ? (
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button size="sm" href="/workspace/employees/new">
              New employee
            </Button>
            <Button variant="outline" size="sm" href="/workspace/employees/templates">
              Browse templates
            </Button>
          </div>
        ) : null
      }
    />
  );
}
