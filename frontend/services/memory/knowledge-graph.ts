import { NODE_HEIGHT, NODE_WIDTH, connectionPath, type CanvasPosition } from "@/services/workflows";
import type { GraphEdge, GraphNode, KnowledgeGraph } from "./types";

/**
 * Knowledge-graph geometry and pure queries. Everything here is a function of
 * the graph — no state, no React, no side effects — so the canvas, the
 * inspector and the memory store all read the same answers.
 *
 * ## What is reused
 *
 * The workflow builder's graph module (`services/workflows/graph.ts`) owns the
 * geometry every canvas in this product shares, and it lives in `services/`
 * precisely so callers outside `features/workflows` can use it. The node box,
 * the bezier and the zoom clamp are imported, not restated — three canvases that
 * curve differently would be three canvases, and these must not drift.
 *
 * ## What is different, and why
 *
 * A knowledge graph is an **association** graph, not a dependency graph. An edge
 * here says "these are related", so the useful question is *what touches this
 * node* in either direction — `neighboursOf` — where the workflow and execution
 * graphs ask "what runs after what". Their `dependenciesOf`/`rootNodes` have no
 * meaning for relationships, so they are not reached for.
 *
 * `boundsOf` is written generically over anything carrying a `position`. The
 * workflow module's `graphBounds` answers the same question but is typed to
 * `WorkflowNode`, so it cannot accept a `GraphNode`; expressing it once
 * generically here is what stops a fourth copy being written next time.
 *
 * Nothing here retrieves, embeds or ranks. It positions a picture.
 */

/** Re-exported so the memory feature has one graph import, not two. */
export {
  NODE_HEIGHT,
  NODE_WIDTH,
  ZOOM_MAX,
  ZOOM_MIN,
  ZOOM_STEP,
  clampZoom,
  connectionPath,
} from "@/services/workflows";

/** Column and row pitch for the deterministic layout. */
export const COLUMN_PITCH = 280;
export const ROW_PITCH = 110;

/** Where a connection leaves a node. */
export const outputAnchor = (node: GraphNode): CanvasPosition => ({
  x: node.position.x + NODE_WIDTH,
  y: node.position.y + NODE_HEIGHT / 2,
});

/** Where a connection arrives at a node. */
export const inputAnchor = (node: GraphNode): CanvasPosition => ({
  x: node.position.x,
  y: node.position.y + NODE_HEIGHT / 2,
});

/** The path drawn between two related nodes. */
export const edgePath = (from: GraphNode, to: GraphNode): string =>
  connectionPath(outputAnchor(from), inputAnchor(to));

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/**
 * Bounding box covering every node, or null for an empty graph.
 *
 * Generic over anything positioned, so any future graph can call this one rather
 * than write its own.
 */
export function boundsOf(nodes: readonly { position: CanvasPosition }[]): Bounds | null {
  const first = nodes[0];
  if (!first) return null;

  return nodes.reduce<Bounds>(
    (acc, node) => ({
      minX: Math.min(acc.minX, node.position.x),
      minY: Math.min(acc.minY, node.position.y),
      maxX: Math.max(acc.maxX, node.position.x + NODE_WIDTH),
      maxY: Math.max(acc.maxY, node.position.y + NODE_HEIGHT),
    }),
    {
      minX: first.position.x,
      minY: first.position.y,
      maxX: first.position.x + NODE_WIDTH,
      maxY: first.position.y + NODE_HEIGHT,
    }
  );
}

export const nodeById = (graph: KnowledgeGraph, id: string | null): GraphNode | null =>
  id === null ? null : (graph.nodes.find((n) => n.id === id) ?? null);

/** Every edge touching `id`, in either direction. */
export const edgesTouching = (graph: KnowledgeGraph, id: string): GraphEdge[] =>
  graph.edges.filter((e) => e.sourceNode === id || e.targetNode === id);

export interface Neighbour {
  node: GraphNode;
  edge: GraphEdge;
  /** True when `id` is the edge's source — it points *out* to this neighbour. */
  isOutgoing: boolean;
}

/**
 * What this node is related to, in either direction, with the edge that says so.
 *
 * The inspector renders these as words and focusable buttons — which is what
 * makes an SVG graph usable by keyboard at all.
 */
export function neighboursOf(graph: KnowledgeGraph, id: string): Neighbour[] {
  return edgesTouching(graph, id).flatMap((edge) => {
    const isOutgoing = edge.sourceNode === id;
    const other = nodeById(graph, isOutgoing ? edge.targetNode : edge.sourceNode);
    return other ? [{ node: other, edge, isOutgoing }] : [];
  });
}

/** Is this edge attached to the given node? Drives edge highlighting. */
export const isEdgeTouching = (edge: GraphEdge, id: string | null): boolean =>
  id !== null && (edge.sourceNode === id || edge.targetNode === id);

/**
 * The graph reduced to one node and what it touches. The workspace's graph panel
 * shows this rather than the whole map, because a memory's neighbourhood is the
 * question being asked there.
 */
export function neighbourhood(graph: KnowledgeGraph, id: string): KnowledgeGraph {
  const edges = edgesTouching(graph, id);
  const keep = new Set<string>([id]);
  edges.forEach((edge) => {
    keep.add(edge.sourceNode);
    keep.add(edge.targetNode);
  });
  return { nodes: graph.nodes.filter((n) => keep.has(n.id)), edges };
}

/**
 * A deterministic layout: kinds occupy columns in a fixed order, and nodes stack
 * within their column in graph order.
 *
 * A knowledge graph has no roots to flow from — an association graph can cycle
 * freely — so depth-from-root (what the execution graph uses) has nothing to
 * measure. Grouping by kind is the stable arrangement that a relationship map
 * can actually guarantee.
 *
 * Fixtures ship their own positions, so this exists for graphs that arrive
 * without them — which is what Sprint 17.9 will get from a backend that
 * describes relations but has no opinion about pixels.
 */
const COLUMN_ORDER: Record<GraphNode["kind"], number> = {
  collection: 0,
  document: 1,
  memory: 2,
  employee: 3,
  workflow: 4,
  task: 5,
};

export function layoutGraph(graph: KnowledgeGraph): KnowledgeGraph {
  const rowCursor = new Map<number, number>();

  const nodes = graph.nodes.map((node) => {
    const column = COLUMN_ORDER[node.kind];
    const row = rowCursor.get(column) ?? 0;
    rowCursor.set(column, row + 1);
    return { ...node, position: { x: 40 + column * COLUMN_PITCH, y: 40 + row * ROW_PITCH } };
  });

  return { nodes, edges: graph.edges };
}
