"use client";

import { memo } from "react";
import { edgePath, type ExecutionNode } from "@/services/tasks";
import { cn } from "@/lib/utils";

export interface ExecutionEdgeProps {
  from: ExecutionNode;
  to: ExecutionNode;
  /** The run actually travelled this edge. */
  isOnPath: boolean;
  /** Either end is the selected node. */
  isActive: boolean;
}

/**
 * A dependency drawn between two nodes: `from` is the node depended on, `to` the
 * node that depends on it.
 *
 * Presentational and non-interactive — an SVG path can't take focus, and every
 * connection a user needs to follow is also listed in the inspector, which works
 * with a pointer and a keyboard alike. That's why this carries no handlers and
 * is hidden from the accessibility tree by the canvas.
 *
 * The bezier itself comes from the workflow builder's graph module, so an
 * execution graph and a workflow graph curve identically.
 */
export const ExecutionEdgeLine = memo(function ExecutionEdgeLine({
  from,
  to,
  isOnPath,
  isActive,
}: ExecutionEdgeProps) {
  return (
    <path
      d={edgePath(from, to)}
      fill="none"
      strokeWidth={isOnPath ? 2.5 : 2}
      strokeLinecap="round"
      markerEnd={isOnPath ? "url(#execution-arrow-path)" : "url(#execution-arrow)"}
      className={cn(
        "transition-colors",
        isActive ? "stroke-primary" : isOnPath ? "stroke-success" : "stroke-border"
      )}
    />
  );
});

/**
 * Arrowheads shared by every edge, rendered once per canvas. Two of them: an
 * edge the run travelled is drawn in the success tone, and its head has to match
 * or the line would change colour at the tip.
 */
export function ExecutionEdgeMarkers() {
  return (
    <defs>
      <marker
        id="execution-arrow"
        viewBox="0 0 10 10"
        refX="9"
        refY="5"
        markerWidth="5"
        markerHeight="5"
        orient="auto-start-reverse"
      >
        <path d="M 0 0 L 10 5 L 0 10 z" className="fill-border" />
      </marker>
      <marker
        id="execution-arrow-path"
        viewBox="0 0 10 10"
        refX="9"
        refY="5"
        markerWidth="5"
        markerHeight="5"
        orient="auto-start-reverse"
      >
        <path d="M 0 0 L 10 5 L 0 10 z" className="fill-success" />
      </marker>
    </defs>
  );
}
