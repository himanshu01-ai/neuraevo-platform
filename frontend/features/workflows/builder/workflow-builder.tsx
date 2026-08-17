"use client";

import { useMemo } from "react";
import { Blocks, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBuilderStore } from "@/store/workflow";
import { WorkflowToolbar } from "../toolbar/workflow-toolbar";
import { StepLibrary } from "../sidebar/step-library";
import { InspectorPanel } from "../inspector/inspector-panel";
import { WorkflowCanvas } from "../canvas/workflow-canvas";
import { CanvasStepper } from "../canvas/canvas-stepper";
import { WorkflowValidationPanel } from "../validation/workflow-validation-panel";
import { WorkflowStatusBar } from "../validation/workflow-status-bar";
import { WorkflowEmptyState } from "../components/workflow-empty-state";
import { useWorkflowValidation } from "../hooks/use-workflow-validation";
import { cn } from "@/lib/utils";

/**
 * The builder shell: toolbar across the top, step library / canvas / inspector
 * in the middle, validation and status along the bottom.
 *
 * Responsive strategy:
 *  - `lg+` — the three-column layout, panels permanent.
 *  - `md`  — canvas keeps the full width; library and inspector slide over it.
 *  - `<md` — the canvas becomes a vertical stepper (docs/11's fallback for this
 *    screen). Dragging a 208px node around a 375px viewport isn't a real
 *    interaction; selecting a step and editing it in the inspector is.
 *
 * The panels are shown/hidden with CSS at `lg`, not a media-query hook, so there
 * is no first-paint flash and nothing to mismatch on hydration.
 */
export function WorkflowBuilder() {
  const graph = useBuilderStore((s) => s.graph);
  const mobilePanel = useBuilderStore((s) => s.mobilePanel);
  const setMobilePanel = useBuilderStore((s) => s.setMobilePanel);
  const isValidationOpen = useBuilderStore((s) => s.isValidationOpen);
  const report = useWorkflowValidation();

  const flaggedNodeIds = useMemo(
    () => [...new Set(report.issues.flatMap((issue) => issue.nodeIds))],
    [report]
  );

  const isEmpty = graph.nodes.length === 0;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkflowToolbar />

      {/* Panel switches. Only below lg, where the panels overlay the canvas. */}
      <div className="flex shrink-0 items-center gap-1 border-b bg-card px-3 py-1.5 lg:hidden">
        <Button
          variant="ghost"
          size="sm"
          className={cn("h-7", mobilePanel === "library" && "bg-accent")}
          aria-pressed={mobilePanel === "library"}
          onClick={() => setMobilePanel(mobilePanel === "library" ? null : "library")}
        >
          <Blocks className="size-3.5" aria-hidden="true" />
          Steps
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={cn("h-7", mobilePanel === "inspector" && "bg-accent")}
          aria-pressed={mobilePanel === "inspector"}
          onClick={() => setMobilePanel(mobilePanel === "inspector" ? null : "inspector")}
        >
          <SlidersHorizontal className="size-3.5" aria-hidden="true" />
          Inspector
        </Button>
      </div>

      <div className="relative flex min-h-0 flex-1">
        <aside
          aria-label="Step library"
          className={cn(
            "w-64 shrink-0 border-r bg-card",
            "absolute inset-y-0 left-0 z-20 shadow-xl lg:static lg:z-auto lg:block lg:shadow-none",
            mobilePanel === "library" ? "block" : "hidden"
          )}
        >
          <StepLibrary />
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1 size-7 lg:hidden"
            onClick={() => setMobilePanel(null)}
            aria-label="Close step library"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </aside>

        <div className="relative min-w-0 flex-1">
          {/* The canvas proper, from md up. */}
          <div className="hidden size-full md:block">
            <WorkflowCanvas flaggedNodeIds={flaggedNodeIds} />
          </div>

          {/* The stepper below md. */}
          <div className="size-full overflow-y-auto md:hidden">
            {isEmpty ? (
              <WorkflowEmptyState
                title="No steps yet"
                description="Open Steps and pick one to begin."
                showActions={false}
              />
            ) : (
              <CanvasStepper graph={graph} />
            )}
          </div>

          {isEmpty ? (
            // Sits over the canvas but never blocks it — a drop still lands.
            <div className="pointer-events-none absolute inset-0 hidden items-center justify-center md:flex">
              <WorkflowEmptyState
                title="Start building"
                description="Drag a step from the library, or click one to drop it here."
                showActions={false}
              />
            </div>
          ) : null}
        </div>

        <aside
          aria-label="Inspector"
          className={cn(
            "w-80 shrink-0 border-l bg-card",
            "absolute inset-y-0 right-0 z-20 shadow-xl lg:static lg:z-auto lg:block lg:shadow-none",
            mobilePanel === "inspector" ? "block" : "hidden"
          )}
        >
          <InspectorPanel />
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1 size-7 lg:hidden"
            onClick={() => setMobilePanel(null)}
            aria-label="Close inspector"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </aside>
      </div>

      {isValidationOpen ? <WorkflowValidationPanel /> : null}
      <WorkflowStatusBar />
    </div>
  );
}
