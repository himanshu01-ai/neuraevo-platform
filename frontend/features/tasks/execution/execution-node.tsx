"use client";

import { memo } from "react";
import { NODE_HEIGHT, NODE_WIDTH, type ExecutionNode as ExecutionNodeModel } from "@/services/tasks";
import { NODE_LABEL, NODE_TONE } from "@/types/domain";
import { TONE_DOT } from "@/components/ui/status-badge";
import { EXECUTION_NODE_META } from "../models/execution-nodes";
import { cn } from "@/lib/utils";

export interface ExecutionNodeProps {
  node: ExecutionNodeModel;
  isSelected: boolean;
  /** The platform says this is the node it's on right now. */
  isCurrent: boolean;
  onSelect: (nodeId: string) => void;
}

/**
 * One node in a run.
 *
 * Read-only by design: a run is something the platform is doing, so there is
 * nothing here to drag, connect or delete. The whole node is a single button —
 * selecting it fills the inspector — which keeps it reachable by keyboard
 * without any of the workflow builder's pointer choreography.
 *
 * Status is said twice over: a toned dot *and* a word, never colour alone. The
 * current node also carries a ring, so "where it is now" survives a screenshot
 * in greyscale.
 *
 * Memoized: a run advancing changes one node's object, so the rest skip
 * re-rendering.
 */
export const ExecutionNodeCard = memo(function ExecutionNodeCard({
  node,
  isSelected,
  isCurrent,
  onSelect,
}: ExecutionNodeProps) {
  const meta = EXECUTION_NODE_META[node.kind];
  const Icon = meta.icon;
  const tone = NODE_TONE[node.status];
  const isRunning = node.status === "RUNNING";

  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      aria-pressed={isSelected}
      aria-label={`${meta.label}: ${node.name} — ${NODE_LABEL[node.status]}${isCurrent ? ", running now" : ""}`}
      className={cn(
        "absolute flex flex-col justify-center gap-1 rounded-md border bg-card p-2.5 text-left shadow-sm transition-all",
        "hover:border-primary/40 hover:shadow-md",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        isSelected && "border-primary ring-2 ring-primary/30",
        !isSelected && isCurrent && "border-info/60 ring-2 ring-info/25",
        node.status === "SKIPPED" && "opacity-60"
      )}
      style={{ left: node.position.x, top: node.position.y, width: NODE_WIDTH, height: NODE_HEIGHT }}
    >
      <span className="flex items-center gap-2">
        <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-sm bg-muted text-muted-foreground">
          <Icon className="size-3.5" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1 truncate text-xs font-semibold text-foreground">{node.name}</span>
        <span
          aria-hidden="true"
          className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone], isRunning && "animate-pulse-glow")}
        />
      </span>

      <span className="flex items-center justify-between gap-2">
        <span className="truncate text-[0.6875rem] text-muted-foreground">{meta.label}</span>
        <span className="shrink-0 text-[0.6875rem] text-muted-foreground">{NODE_LABEL[node.status]}</span>
      </span>
    </button>
  );
});
