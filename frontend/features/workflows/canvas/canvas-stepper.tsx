"use client";

import { ArrowDown } from "lucide-react";
import { dependenciesOf, type WorkflowGraph } from "@/services/workflows";
import { StatusBadge } from "@/components/ui/status-badge";
import { useBuilderStore } from "@/store/workflow";
import { NODE_TYPES } from "../models/node-types";
import { cn } from "@/lib/utils";

/**
 * The canvas's small-screen form: a vertical stepper instead of a pan/zoom
 * surface, as docs/11 specifies for the workflow screen on mobile.
 *
 * Dragging a node around a viewport narrower than the node itself is not a real
 * interaction, so on mobile the graph is presented as an ordered list you can
 * select from and edit through the inspector. Same store, same draft — only the
 * spatial editing is dropped, which is the part a phone can't do well anyway.
 */
export function CanvasStepper({ graph }: { graph: WorkflowGraph }) {
  const selectedNodeId = useBuilderStore((s) => s.selectedNodeId);
  const selectNode = useBuilderStore((s) => s.selectNode);

  return (
    <ol className="space-y-2 p-4">
      {graph.nodes.map((node, index) => {
        const meta = NODE_TYPES[node.kind];
        const Icon = meta.icon;
        const dependencies = dependenciesOf(graph, node.id);

        return (
          <li key={node.id}>
            {index > 0 ? (
              <ArrowDown className="mx-auto my-1 size-4 text-muted-foreground/50" aria-hidden="true" />
            ) : null}
            <button
              type="button"
              aria-pressed={selectedNodeId === node.id}
              onClick={() => selectNode(node.id)}
              className={cn(
                "flex w-full items-start gap-3 rounded-md border bg-card p-3 text-left shadow-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                selectedNodeId === node.id ? "border-primary ring-2 ring-primary" : "hover:bg-accent"
              )}
            >
              <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">{node.name}</span>
                <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                  {meta.label}
                  {dependencies.length > 0 ? ` · after ${dependencies.length} step${dependencies.length === 1 ? "" : "s"}` : ""}
                </span>
              </span>
              {node.status !== "PENDING" ? <StatusBadge kind="node" status={node.status} /> : null}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
