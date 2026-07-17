"use client";

import { Share2 } from "lucide-react";
import {
  RELATIONSHIP_LABEL,
  neighboursOf,
  type KnowledgeGraph,
  type MemoryDetail,
} from "@/services/memory";
import { useMemoryStore } from "@/store/memory";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { GRAPH_NODE_META } from "../models/graph-nodes";
import { cn } from "@/lib/utils";

export interface RelationshipListProps {
  memory: MemoryDetail;
  graph: KnowledgeGraph;
  className?: string;
}

/**
 * What this memory touches, in words.
 *
 * This is the graph's accessible twin: the SVG edges are decorative and can't
 * take focus, so every association is also stated here as a focusable row that
 * names the other end, the relationship, and which way it points. Selecting a
 * row moves the graph's selection, so the two views stay in step.
 */
export function RelationshipList({ memory, graph, className }: RelationshipListProps) {
  const selectGraphNode = useMemoryStore((s) => s.selectGraphNode);
  const selectedGraphNodeId = useMemoryStore((s) => s.selectedGraphNodeId);

  const anchor = graph.nodes.find((n) => n.memoryId === memory.id) ?? null;
  const neighbours = anchor ? neighboursOf(graph, anchor.id) : [];

  if (neighbours.length === 0) {
    return (
      <EmptyState
        compact
        icon={Share2}
        title="Nothing connected"
        description="This memory isn't linked to anything in the knowledge graph yet."
        className={className}
      />
    );
  }

  return (
    <ul className={cn("grid gap-2 sm:grid-cols-2", className)}>
      {neighbours.map(({ node, edge, isOutgoing }) => {
        const meta = GRAPH_NODE_META[node.kind];
        const Icon = meta.icon;
        const isSelected = selectedGraphNodeId === node.id;

        return (
          <li key={edge.id}>
            <button
              type="button"
              onClick={() => selectGraphNode(node.id)}
              aria-pressed={isSelected}
              className={cn(
                "flex w-full items-start gap-3 rounded-md border p-3 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isSelected ? "border-primary/40 bg-primary/5" : "border-border hover:bg-accent"
              )}
            >
              <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <Icon className="size-4" aria-hidden="true" />
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">{node.name}</span>
                <span className="block truncate text-xs text-muted-foreground">{node.detail}</span>
                <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <Badge variant="outline">{meta.label}</Badge>
                  {/* Direction said in words: "references" vs "is referenced by". */}
                  <Badge variant="default">
                    {isOutgoing
                      ? RELATIONSHIP_LABEL[edge.relationship]
                      : `is ${RELATIONSHIP_LABEL[edge.relationship]} this`}
                  </Badge>
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
