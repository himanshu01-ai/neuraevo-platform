"use client";

import { memo } from "react";
import { NODE_HEIGHT, NODE_WIDTH, type GraphNode } from "@/services/memory";
import { GRAPH_NODE_META } from "../models/graph-nodes";
import { cn } from "@/lib/utils";

export interface KnowledgeGraphNodeProps {
  node: GraphNode;
  isSelected: boolean;
  /** This node stands for the memory currently open in the workspace. */
  isFocus: boolean;
  onSelect: (nodeId: string) => void;
}

/**
 * One node in the knowledge graph.
 *
 * Read-only: relationships are the platform's account of how the knowledge hangs
 * together, so there is nothing here to drag, connect or delete. The whole node
 * is a single button — selecting it fills the inspector — which keeps it
 * reachable by keyboard without any of the workflow builder's pointer
 * choreography.
 *
 * The focus node carries a ring rather than a colour, because colour in this
 * system carries status and a node in a relationship map has none.
 *
 * Memoized: selecting one node changes one node's props, so the rest skip
 * re-rendering.
 */
export const KnowledgeGraphNode = memo(function KnowledgeGraphNode({
  node,
  isSelected,
  isFocus,
  onSelect,
}: KnowledgeGraphNodeProps) {
  const meta = GRAPH_NODE_META[node.kind];
  const Icon = meta.icon;

  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      aria-pressed={isSelected}
      aria-label={`${meta.label}: ${node.name}${isFocus ? ", the memory in view" : ""}`}
      className={cn(
        "absolute flex flex-col justify-center gap-1 rounded-md border bg-card p-2.5 text-left shadow-sm transition-all",
        "hover:border-primary/40 hover:shadow-md",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        isSelected && "border-primary ring-2 ring-primary/30",
        !isSelected && isFocus && "border-primary/50 ring-2 ring-primary/20"
      )}
      style={{ left: node.position.x, top: node.position.y, width: NODE_WIDTH, height: NODE_HEIGHT }}
    >
      <span className="flex items-center gap-2">
        <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-sm bg-muted text-muted-foreground">
          <Icon className="size-3.5" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1 truncate text-xs font-semibold text-foreground">{node.name}</span>
      </span>

      <span className="flex items-center justify-between gap-2">
        <span className="truncate text-[0.6875rem] text-muted-foreground">{meta.label}</span>
      </span>
    </button>
  );
});
