"use client";

import { memo } from "react";
import { connectionPath, type CanvasPosition } from "@/services/workflows";
import { cn } from "@/lib/utils";

export interface WorkflowConnectionProps {
  from: CanvasPosition;
  to: CanvasPosition;
  /** A connection being drawn, not yet committed. */
  isDraft?: boolean;
  /** Either end is the selected node. */
  isActive?: boolean;
}

/**
 * A dependency drawn between two steps: `from` is the step depended on, `to` the
 * step that depends on it.
 *
 * Presentational and non-interactive — connections are managed from the
 * inspector's Connections list, which works with a pointer and a keyboard alike.
 * An SVG path can do neither.
 */
export const WorkflowConnection = memo(function WorkflowConnection({
  from,
  to,
  isDraft = false,
  isActive = false,
}: WorkflowConnectionProps) {
  return (
    <path
      d={connectionPath(from, to)}
      fill="none"
      strokeWidth={2}
      strokeLinecap="round"
      markerEnd={isDraft ? undefined : "url(#workflow-arrow)"}
      strokeDasharray={isDraft ? "5 5" : undefined}
      className={cn(
        "transition-colors",
        isDraft ? "stroke-primary" : isActive ? "stroke-primary" : "stroke-border"
      )}
    />
  );
});

/** Arrowhead shared by every committed connection. Rendered once per canvas. */
export function ConnectionMarkers() {
  return (
    <defs>
      <marker
        id="workflow-arrow"
        viewBox="0 0 10 10"
        refX="9"
        refY="5"
        markerWidth="5"
        markerHeight="5"
        orient="auto-start-reverse"
      >
        <path d="M 0 0 L 10 5 L 0 10 z" className="fill-border" />
      </marker>
    </defs>
  );
}
