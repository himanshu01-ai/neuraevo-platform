import Link from "next/link";
import { Workflow } from "lucide-react";
import type { EmployeeAssignments } from "@/services/employees";
import { EXECUTION_MODE_LABEL, PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Progress } from "@/components/ui/progress";
import { StatusBadge, TONE_VARIANT } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";

export interface AssignmentPanelProps {
  assignments: EmployeeAssignments;
  className?: string;
}

/**
 * What this employee is on: the workflows assigned to it, the task it's on right
 * now, and what's waiting.
 *
 * Read-only by design. Assignment is a description here; the platform is what
 * schedules, orders, and runs the work, so nothing on this surface starts,
 * stops, or reorders anything. Sprint 17.7 wires the real thing behind it.
 */
export function AssignmentPanel({ assignments, className }: AssignmentPanelProps) {
  const { workflows, currentTask, queue } = assignments;
  const isIdle = workflows.length === 0 && currentTask === null && queue.length === 0;

  if (isIdle) {
    return (
      <EmptyState
        compact
        icon={Workflow}
        title="Nothing assigned"
        description="This employee isn't on any workflows yet."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Current task</h4>
        {currentTask ? (
          <div className="mt-2 rounded-md border bg-background p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{currentTask.title}</p>
                <p className="truncate text-xs text-muted-foreground">in {currentTask.workflowName}</p>
              </div>
              <StatusBadge kind="lifecycle" status={currentTask.status} />
            </div>
            <Progress
              value={currentTask.progress}
              label={`${currentTask.title} progress`}
              className="mt-3"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">{currentTask.progress}% complete</p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">Not working on anything right now.</p>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Assigned workflows
        </h4>
        {workflows.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No workflows assigned.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {workflows.map((assignment) => (
              <li key={assignment.workflowId} className="rounded-md border bg-background p-3">
                <div className="flex items-start justify-between gap-2">
                  <h5 className="min-w-0 text-sm font-medium">
                    <Link
                      href={`/workspace/workflows/${assignment.workflowId}`}
                      className="block truncate rounded-sm text-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {assignment.workflowName}
                    </Link>
                  </h5>
                  <Badge variant={TONE_VARIANT[PRIORITY_TONE[assignment.priority]]} className="shrink-0">
                    {PRIORITY_LABEL[assignment.priority]}
                  </Badge>
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">{assignment.dependencySummary}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  <span className="text-foreground">{EXECUTION_MODE_LABEL[assignment.executionMode]}</span>{" "}
                  execution
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Queue{queue.length > 0 ? ` (${queue.length})` : ""}
        </h4>
        {queue.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">Nothing waiting.</p>
        ) : (
          <ol className="mt-2 space-y-1.5">
            {queue.map((item) => (
              <li key={item.id} className="flex items-center gap-3 rounded-md border bg-background px-3 py-2">
                <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                  {item.position}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm text-foreground">{item.title}</span>
                <Badge variant={TONE_VARIANT[PRIORITY_TONE[item.priority]]} className="shrink-0">
                  {PRIORITY_LABEL[item.priority]}
                </Badge>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
