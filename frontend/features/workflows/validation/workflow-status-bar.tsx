"use client";

import { CircleCheck, Info, TriangleAlert } from "lucide-react";
import { useBuilderStore } from "@/store/workflow";
import { useWorkflowValidation } from "../hooks/use-workflow-validation";
import { cn } from "@/lib/utils";

/**
 * The builder's footer: how big the workflow is, what validation says, and
 * whether there are unsaved changes.
 *
 * `notice` is the transient line — a refused connection, an import result. It's
 * announced politely so a keyboard user hears why a connection didn't take.
 */
export function WorkflowStatusBar() {
  const nodeCount = useBuilderStore((s) => s.graph.nodes.length);
  const edgeCount = useBuilderStore((s) => s.graph.edges.length);
  const isDirty = useBuilderStore((s) => s.isDirty);
  const notice = useBuilderStore((s) => s.notice);
  const setValidationOpen = useBuilderStore((s) => s.setValidationOpen);
  const report = useWorkflowValidation();

  const hasIssues = report.issues.length > 0;

  return (
    <footer className="flex h-9 shrink-0 items-center justify-between gap-3 border-t bg-card/40 px-4 text-xs">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={() => setValidationOpen(true)}
          className={cn(
            // min-h-6: a 20px-tall control would miss the 24px target minimum.
            "flex min-h-6 items-center gap-1.5 rounded-sm px-1.5 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            hasIssues ? "text-foreground hover:bg-accent" : "text-muted-foreground hover:bg-accent"
          )}
        >
          {hasIssues ? (
            <TriangleAlert
              className={cn("size-3.5", report.errorCount > 0 ? "text-destructive" : "text-warning")}
              aria-hidden="true"
            />
          ) : (
            <CircleCheck className="size-3.5 text-success" aria-hidden="true" />
          )}
          {hasIssues
            ? `${report.issues.length} issue${report.issues.length === 1 ? "" : "s"}`
            : "No issues"}
        </button>

        {notice ? (
          <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
            <Info className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{notice}</span>
          </span>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-3 text-muted-foreground">
        <span>
          {nodeCount} step{nodeCount === 1 ? "" : "s"} · {edgeCount} connection{edgeCount === 1 ? "" : "s"}
        </span>
        <span className={cn(isDirty ? "text-warning" : "text-muted-foreground")}>
          {isDirty ? "Unsaved changes" : "Saved"}
        </span>
      </div>

      {/* Politely announce the transient line without moving focus. */}
      <span aria-live="polite" className="sr-only">
        {notice ?? ""}
      </span>
    </footer>
  );
}
