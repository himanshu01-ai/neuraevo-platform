import { CircleCheck, TriangleAlert } from "lucide-react";
import { nodeById, type ExecutionGraph, type ExecutionMonitor as ExecutionMonitorModel } from "@/services/tasks";
import { StatusBadge } from "@/components/ui/status-badge";
import { Progress } from "@/components/ui/progress";
import { EXECUTION_NODE_META } from "../models/execution-nodes";
import { TaskStateBadge } from "../components/task-state-badge";
import { cn } from "@/lib/utils";

export interface ExecutionMonitorProps {
  monitor: ExecutionMonitorModel;
  graph: ExecutionGraph;
  className?: string;
}

/**
 * What the platform says about a run: where it stands, how healthy it is, what
 * it's on, and what it's complaining about.
 *
 * Every number here is carried, not computed. The step count and the percentage
 * are the platform's own — showing "3 of 8" beside a 62% bar that the UI derived
 * from those same numbers would be inventing a second opinion about a fact only
 * the backend holds.
 */
export function ExecutionMonitor({ monitor, graph, className }: ExecutionMonitorProps) {
  const current = nodeById(graph, monitor.currentNodeId);
  const hasIssues = monitor.warnings.length > 0 || monitor.errors.length > 0;

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex flex-wrap items-center gap-1.5">
        <TaskStateBadge state={monitor.state} />
        <StatusBadge kind="health" status={monitor.health} />
      </div>

      <div>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm text-muted-foreground">Progress</span>
          <span className="text-sm font-medium tabular-nums text-foreground">{monitor.progress}%</span>
        </div>
        <Progress value={monitor.progress} label="Execution progress" className="mt-1.5" />
        <p className="mt-1.5 text-xs text-muted-foreground">
          {monitor.completedSteps} of {monitor.totalSteps} step{monitor.totalSteps === 1 ? "" : "s"} complete
        </p>
      </div>

      <div className="rounded-md border bg-background p-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Current node</h4>
        {current ? (
          <div className="mt-2 flex items-center gap-2.5">
            <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-sm bg-muted text-muted-foreground">
              {(() => {
                const Icon = EXECUTION_NODE_META[current.kind].icon;
                return <Icon className="size-4" aria-hidden="true" />;
              })()}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-foreground">{current.name}</span>
              <span className="block truncate text-xs text-muted-foreground">{current.detail}</span>
            </span>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">Not on anything right now.</p>
        )}
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Execution path</h4>
        {monitor.executionPath.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">Nothing has run yet.</p>
        ) : (
          <ol className="mt-2 flex flex-wrap items-center gap-1">
            {monitor.executionPath.map((nodeId, index) => {
              const node = nodeById(graph, nodeId);
              if (!node) return null;
              return (
                <li key={nodeId} className="flex items-center gap-1">
                  {index > 0 ? (
                    <span aria-hidden="true" className="text-muted-foreground">
                      ·
                    </span>
                  ) : null}
                  <span
                    className={cn(
                      "inline-flex items-center rounded-sm px-1.5 py-0.5 text-xs",
                      nodeId === monitor.currentNodeId
                        ? "bg-info/10 font-medium text-info"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {node.name}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Warnings and errors
        </h4>
        {!hasIssues ? (
          <p className="mt-2 flex items-start gap-2 text-sm text-muted-foreground">
            <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
            Nothing to report.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {[
              ...monitor.errors.map((issue) => ({ issue, isError: true })),
              ...monitor.warnings.map((issue) => ({ issue, isError: false })),
            ].map(({ issue, isError }) => {
              const node = nodeById(graph, issue.nodeId);
              return (
                <li key={issue.id} className="flex items-start gap-2 text-sm">
                  <TriangleAlert
                    className={cn("mt-0.5 size-4 shrink-0", isError ? "text-destructive" : "text-warning")}
                    aria-hidden="true"
                  />
                  <span className="min-w-0">
                    {/* The severity is said, not just coloured. */}
                    <span className="sr-only">{isError ? "Error: " : "Warning: "}</span>
                    <span className="text-foreground">{issue.message}</span>
                    {node ? <span className="block text-xs text-muted-foreground">at {node.name}</span> : null}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
