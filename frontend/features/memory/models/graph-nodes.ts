import { Bot, Brain, FileText, Folder, ListChecks, Workflow, type LucideIcon } from "lucide-react";
import { GRAPH_NODE_KINDS, type GraphNodeKind } from "@/services/memory";

/**
 * What each node in the knowledge graph stands for, and how it looks.
 *
 * The icons deliberately match the rest of the app: a workflow is the same glyph
 * here as in the workflow builder, an employee the same as in the directory, a
 * task the same as on the board. A knowledge graph is a map *of* the product, so
 * its landmarks should be recognisable from the places they point to.
 *
 * Nodes are neutral. Colour carries status in this system, and a node in a
 * relationship map doesn't have one.
 */

export interface GraphNodeMeta {
  kind: GraphNodeKind;
  label: string;
  icon: LucideIcon;
}

export const GRAPH_NODE_META: Record<GraphNodeKind, GraphNodeMeta> = {
  memory: { kind: "memory", label: "Memory", icon: Brain },
  employee: { kind: "employee", label: "AI Employee", icon: Bot },
  workflow: { kind: "workflow", label: "Workflow", icon: Workflow },
  task: { kind: "task", label: "Task", icon: ListChecks },
  document: { kind: "document", label: "Document", icon: FileText },
  collection: { kind: "collection", label: "Collection", icon: Folder },
};

/** Every node kind in canonical order. */
export const GRAPH_NODE_LIST: readonly GraphNodeMeta[] = GRAPH_NODE_KINDS.map(
  (kind) => GRAPH_NODE_META[kind]
);
