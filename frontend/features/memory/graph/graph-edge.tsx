"use client";

import { memo } from "react";
import { RELATIONSHIP_LABEL, edgePath, type GraphEdge, type GraphNode } from "@/services/memory";
import { inputAnchor, outputAnchor } from "@/services/memory";
import { cn } from "@/lib/utils";

export interface KnowledgeGraphEdgeProps {
  from: GraphNode;
  to: GraphNode;
  edge: GraphEdge;
  /** Either end is the selected node. */
  isActive: boolean;
  /** Draw the relationship's name along the line. Off in dense views. */
  showLabel?: boolean;
}

/**
 * A relationship drawn between two nodes: `from` → `to`.
 *
 * Presentational and non-interactive — an SVG path can't take focus, and every
 * relationship a user needs to follow is also listed in the inspector, in words
 * and as focusable buttons. That's why this carries no handlers and the canvas
 * hides it from the accessibility tree.
 *
 * The bezier comes from the workflow builder's graph module, so a knowledge
 * graph, an execution graph and a workflow curve identically.
 */
export const KnowledgeGraphEdge = memo(function KnowledgeGraphEdge({
  from,
  to,
  edge,
  isActive,
  showLabel = false,
}: KnowledgeGraphEdgeProps) {
  const path = edgePath(from, to);
  const start = outputAnchor(from);
  const end = inputAnchor(to);

  return (
    <g>
      <path
        d={path}
        fill="none"
        strokeWidth={isActive ? 2.5 : 2}
        strokeLinecap="round"
        markerEnd={isActive ? "url(#knowledge-arrow-active)" : "url(#knowledge-arrow)"}
        className={cn("transition-colors", isActive ? "stroke-primary" : "stroke-border")}
      />

      {showLabel ? (
        // Sits at the midpoint of the anchors rather than on the curve: close
        // enough to read as the line's label, and cheap to place.
        <text
          x={(start.x + end.x) / 2}
          y={(start.y + end.y) / 2 - 6}
          textAnchor="middle"
          className={cn(
            "select-none text-[10px]",
            isActive ? "fill-primary" : "fill-muted-foreground"
          )}
        >
          {RELATIONSHIP_LABEL[edge.relationship]}
        </text>
      ) : null}
    </g>
  );
});

/**
 * Arrowheads shared by every edge, rendered once per canvas. Two of them: an
 * active edge is drawn in the primary tone, and its head has to match or the
 * line would change colour at the tip.
 */
export function KnowledgeGraphMarkers() {
  return (
    <defs>
      <marker
        id="knowledge-arrow"
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
        id="knowledge-arrow-active"
        viewBox="0 0 10 10"
        refX="9"
        refY="5"
        markerWidth="5"
        markerHeight="5"
        orient="auto-start-reverse"
      >
        <path d="M 0 0 L 10 5 L 0 10 z" className="fill-primary" />
      </marker>
    </defs>
  );
}
