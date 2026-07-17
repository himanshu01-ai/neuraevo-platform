"use client";

import { useMemoryStore } from "@/store/memory";
import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/error-state";
import { useKnowledgeGraph, useMemoryDetail } from "../hooks/use-memory";
import { GRAPH_NODE_LIST } from "../models/graph-nodes";
import { GraphLoading } from "../components/memory-states";
import { MemoryInspector } from "../components/memory-inspector";
import { KnowledgeGraph } from "./knowledge-graph";
import { nodeById } from "@/services/memory";

/**
 * The whole knowledge map, with a legend and whatever you've selected.
 *
 * Selecting a node that stands for a memory fills the panel beside it; selecting
 * an employee, workflow or task doesn't, because those live in their own
 * modules and this map only holds a name and a line — following it there is what
 * the inspector's links are for.
 */
export function KnowledgeGraphScreen() {
  const graph = useKnowledgeGraph();
  const selectedGraphNodeId = useMemoryStore((s) => s.selectedGraphNodeId);

  const selectedNode = graph.data ? nodeById(graph.data, selectedGraphNodeId) : null;
  const detail = useMemoryDetail(selectedNode?.memoryId ?? null);

  if (graph.isPending) return <GraphLoading className="h-[32rem]" />;

  if (graph.isError || !graph.data) {
    return (
      <ErrorState
        title="Couldn't load the knowledge graph"
        description="How the knowledge connects couldn't be loaded. Try again in a moment."
        onRetry={() => void graph.refetch()}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="min-w-0 flex-1">
          <KnowledgeGraph graph={graph.data} showLabels className="h-[32rem]" />
        </div>

        <aside className="min-w-0 xl:w-80 xl:shrink-0">
          <section className="rounded-lg border bg-card p-4 shadow-sm xl:max-h-[32rem] xl:overflow-y-auto">
            {detail.data ? (
              <MemoryInspector memory={detail.data} graph={graph.data} />
            ) : selectedNode ? (
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-foreground">{selectedNode.name}</h2>
                <p className="text-sm text-muted-foreground">{selectedNode.detail}</p>
                <p className="text-xs text-muted-foreground">
                  This is {selectedNode.kind === "employee" ? "an" : "a"} {selectedNode.kind}, not a
                  memory — it lives in its own part of the workspace.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-foreground">Nothing selected</h2>
                <p className="text-sm text-muted-foreground">
                  Pick a node to see what it is and what it touches.
                </p>
              </div>
            )}
          </section>
        </aside>
      </div>

      <section aria-labelledby="graph-legend" className="rounded-lg border bg-card p-4 shadow-sm">
        <h2 id="graph-legend" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Legend
        </h2>
        <ul className="mt-2 flex flex-wrap gap-2">
          {GRAPH_NODE_LIST.map((meta) => {
            const Icon = meta.icon;
            return (
              <li key={meta.kind}>
                <Badge variant="outline">
                  <Icon className="size-3 shrink-0" aria-hidden="true" />
                  {meta.label}
                </Badge>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
