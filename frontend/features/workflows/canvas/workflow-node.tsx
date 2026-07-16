"use client";

import { memo, type PointerEvent as ReactPointerEvent } from "react";
import { NODE_HEIGHT, NODE_WIDTH, type WorkflowNode as WorkflowNodeModel } from "@/services/workflows";
import { StatusBadge } from "@/components/ui/status-badge";
import { NODE_TYPES } from "../models/node-types";
import { cn } from "@/lib/utils";

export interface WorkflowNodeProps {
  node: WorkflowNodeModel;
  isSelected: boolean;
  /** The validation panel flags this node. */
  isFlagged?: boolean;
  /** A connection is being drawn and this node could receive it. */
  isConnectTarget?: boolean;
  onPointerDownCard: (event: ReactPointerEvent, nodeId: string) => void;
  onPointerDownHandle: (event: ReactPointerEvent, nodeId: string) => void;
  onSelect: (nodeId: string) => void;
}

/**
 * One step on the canvas.
 *
 * The card and the connect handle are sibling buttons rather than nested ones —
 * a control inside a control is invalid and unreachable by keyboard. The card
 * body handles select/drag; the handle starts a connection.
 *
 * Selection is wired to both pointerdown (so a drag selects immediately, before
 * it moves anything) and click — a keyboard Enter/Space fires click and no
 * pointer event at all, so without both the canvas would be unreachable by
 * keyboard. Selecting twice on a mouse press is idempotent.
 *
 * Status is only rendered when there is a status to report. Authoring leaves
 * every node PENDING, and a badge reading "Pending" on all fourteen steps is
 * noise; when a run reports something else, the badge appears with dot *and*
 * label, never color alone.
 *
 * Memoized: dragging one node changes only that node's object, so the rest skip
 * re-rendering.
 */
export const WorkflowNode = memo(function WorkflowNode({
  node,
  isSelected,
  isFlagged = false,
  isConnectTarget = false,
  onPointerDownCard,
  onPointerDownHandle,
  onSelect,
}: WorkflowNodeProps) {
  const meta = NODE_TYPES[node.kind];
  const Icon = meta.icon;

  return (
    <div
      data-node-id={node.id}
      role="group"
      aria-label={`${meta.label} step: ${node.name}`}
      className="absolute"
      style={{ left: node.position.x, top: node.position.y, width: NODE_WIDTH, height: NODE_HEIGHT }}
    >
      <button
        type="button"
        aria-pressed={isSelected}
        onPointerDown={(event) => onPointerDownCard(event, node.id)}
        onClick={() => onSelect(node.id)}
        className={cn(
          "flex size-full cursor-grab items-start gap-2.5 rounded-md border bg-card p-3 text-left shadow-sm transition-[box-shadow,border-color,transform]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          "hover:shadow-md active:cursor-grabbing",
          isSelected && "border-primary ring-2 ring-primary",
          isFlagged && !isSelected && "border-warning",
          isConnectTarget && "border-info"
        )}
      >
        <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Icon className="size-4" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">{node.name}</span>
          <span className="mt-0.5 flex items-center gap-1.5">
            <span className="truncate text-xs text-muted-foreground">{meta.label}</span>
            {node.status !== "PENDING" ? <StatusBadge kind="node" status={node.status} /> : null}
          </span>
        </span>
      </button>

      {/* The dot reads as 14px but the button is a 24px target (WCAG 2.5.8):
          the padding is transparent, the inner span is the visible handle. */}
      <button
        type="button"
        aria-label={`Connect from ${node.name}`}
        title={`Connect from ${node.name}`}
        onPointerDown={(event) => onPointerDownHandle(event, node.id)}
        className="group/handle absolute right-0 top-1/2 z-10 flex size-6 -translate-y-1/2 translate-x-1/2 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span
          className={cn(
            "size-3.5 rounded-full border-2 border-background bg-muted-foreground transition-colors group-hover/handle:bg-primary",
            isSelected && "bg-primary"
          )}
        />
      </button>

      {/* Where an incoming connection lands. Marked for the eye, not the pointer. */}
      <span
        aria-hidden="true"
        className="absolute left-0 top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-border"
      />
    </div>
  );
});
