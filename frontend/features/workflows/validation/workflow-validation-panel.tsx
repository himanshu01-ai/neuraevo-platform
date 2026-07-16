"use client";

import { CircleCheck, TriangleAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBuilderStore } from "@/store/workflow";
import { useWorkflowValidation } from "../hooks/use-workflow-validation";
import { cn } from "@/lib/utils";

/**
 * What validation found, and where. Reporting only — it never repairs a graph
 * and never runs one.
 *
 * An issue that points at steps is a button: it selects and centers the first
 * one, so "disconnected step" leads straight to the step.
 */
export function WorkflowValidationPanel() {
  const report = useWorkflowValidation();
  const setValidationOpen = useBuilderStore((s) => s.setValidationOpen);
  const centerOnNode = useBuilderStore((s) => s.centerOnNode);

  return (
    <div className="flex max-h-56 min-h-0 flex-col border-t bg-card">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b px-4 py-2">
        <h2 className="text-sm font-semibold text-foreground">
          Validation
          <span className="ml-2 font-normal text-muted-foreground">
            {report.issues.length === 0
              ? "no issues"
              : `${report.errorCount} error${report.errorCount === 1 ? "" : "s"}, ${report.warningCount} warning${report.warningCount === 1 ? "" : "s"}`}
          </span>
        </h2>
        <Button
          variant="ghost"
          size="icon"
          className="size-7 text-muted-foreground"
          onClick={() => setValidationOpen(false)}
          aria-label="Close validation"
        >
          <X className="size-4" aria-hidden="true" />
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {report.issues.length === 0 ? (
          <p className="flex items-center gap-2 px-1 py-2 text-sm text-muted-foreground">
            <CircleCheck className="size-4 text-success" aria-hidden="true" />
            This workflow is structurally sound. The platform makes the final call on readiness.
          </p>
        ) : (
          <ul className="space-y-1">
            {report.issues.map((issue) => {
              const target = issue.nodeIds[0];
              const content = (
                <>
                  <TriangleAlert
                    className={cn("mt-0.5 size-4 shrink-0", issue.severity === "error" ? "text-destructive" : "text-warning")}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-foreground">{issue.message}</span>
                    <span className="text-xs text-muted-foreground">
                      {issue.severity === "error" ? "Error" : "Warning"}
                      {target ? " · select the step" : ""}
                    </span>
                  </span>
                </>
              );

              return (
                <li key={`${issue.rule}-${issue.message}`}>
                  {target ? (
                    <button
                      type="button"
                      onClick={() => centerOnNode(target)}
                      className="flex w-full items-start gap-2.5 rounded-md p-2 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {content}
                    </button>
                  ) : (
                    <div className="flex items-start gap-2.5 p-2">{content}</div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
