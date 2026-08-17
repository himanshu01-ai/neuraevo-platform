import {
  NODE_HEIGHT,
  NODE_WIDTH,
  connectionPath,
  type CanvasPosition,
} from "@/services/workflows";
import type { ExecutionGraph, ExecutionNode } from "./types";

/**
 * Execution-graph geometry and pure queries. Everything here is a function of
 * the graph — no state, no React, no side effects — so the canvas, the
 * inspector, the monitor and the execution store all read the same answers.
 *
 * The workflow builder's graph module (`services/workflows/graph.ts`) already
 * owns this geometry, and it lives in `services/` precisely so callers outside
 * `features/workflows` can share it. So the node box, the bezier and the zoom
 * clamp are imported, not restated — an execution graph and a workflow graph
 * draw the same way, and they should never drift apart by a pixel.
 *
 * What is defined here is what that module can't answer: the traversal is over
 * `ExecutionNode` (a different node vocabulary), and the run-specific
 * questions — where a run has been, where it is now — have no meaning for a
 * workflow definition at rest.
 *
 * Terminology follows the backend's dependency graph: an edge
 * `sourceNode -> targetNode` means the target depends on the source.
 */

/** Re-exported so the tasks feature has one graph import, not two. */
export { NODE_HEIGHT, NODE_WIDTH, ZOOM_MAX, ZOOM_MIN, ZOOM_STEP, clampZoom, connectionPath } from "@/services/workflows";

/** Column and row pitch for the deterministic layout. */
export const COLUMN_PITCH = 260;
export const ROW_PITCH = 120;

/** Where a connection leaves a node. */
export const outputAnchor = (node: ExecutionNode): CanvasPosition => ({
  x: node.position.x + NODE_WIDTH,
  y: node.position.y + NODE_HEIGHT / 2,
});

/** Where a connection arrives at a node. */
export const inputAnchor = (node: ExecutionNode): CanvasPosition => ({
  x: node.position.x,
  y: node.position.y + NODE_HEIGHT / 2,
});

/** The path drawn between two connected nodes. */
export const edgePath = (from: ExecutionNode, to: ExecutionNode): string =>
  connectionPath(outputAnchor(from), inputAnchor(to));

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** Bounding box covering every node, or null for an empty graph. */
export function graphBounds(nodes: readonly ExecutionNode[]): Bounds | null {
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

/** Node ids `id` depends on. */
export const dependenciesOf = (graph: ExecutionGraph, id: string): string[] =>
  graph.edges.filter((e) => e.targetNode === id).map((e) => e.sourceNode);

/** Node ids that depend on `id`. */
export const dependentsOf = (graph: ExecutionGraph, id: string): string[] =>
  graph.edges.filter((e) => e.sourceNode === id).map((e) => e.targetNode);

/** Nodes with no dependencies — where the run started. */
export const rootNodes = (graph: ExecutionGraph): ExecutionNode[] =>
  graph.nodes.filter((n) => !graph.edges.some((e) => e.targetNode === n.id));

/** Nodes with no dependents — where the run ends. */
export const leafNodes = (graph: ExecutionGraph): ExecutionNode[] =>
  graph.nodes.filter((n) => !graph.edges.some((e) => e.sourceNode === n.id));

export const nodeById = (graph: ExecutionGraph, id: string | null): ExecutionNode | null =>
  id === null ? null : (graph.nodes.find((n) => n.id === id) ?? null);

/**
 * Is this edge part of the path the run actually took? True only when both ends
 * have been visited *and* they were visited in this edge's direction — a run
 * that reached two nodes by different branches didn't travel between them.
 */
export function isEdgeOnPath(path: readonly string[], sourceNode: string, targetNode: string): boolean {
  const from = path.indexOf(sourceNode);
  const to = path.indexOf(targetNode);
  return from !== -1 && to !== -1 && from < to;
}

/**
 * A deterministic left-to-right layout: a node sits one column right of its
 * deepest dependency, and nodes sharing a column stack in graph order.
 *
 * Fixtures ship their own positions, so this exists for graphs that arrive
 * without them — which is what Sprint 17.8 will get from a backend that
 * describes dependencies but has no opinion about pixels.
 */
export function layoutGraph(graph: ExecutionGraph): ExecutionGraph {
  const depth = new Map<string, number>();

  /** Longest path back to a root. Memoized, and cycle-safe via `seen`. */
  const depthOf = (id: string, seen: Set<string>): number => {
    const cached = depth.get(id);
    if (cached !== undefined) return cached;
    if (seen.has(id)) return 0;
    seen.add(id);

    const parents = dependenciesOf(graph, id);
    const value = parents.length === 0 ? 0 : Math.max(...parents.map((p) => depthOf(p, seen))) + 1;
    depth.set(id, value);
    return value;
  };

  const rowCursor = new Map<number, number>();
  const nodes = graph.nodes.map((node) => {
    const column = depthOf(node.id, new Set());
    const row = rowCursor.get(column) ?? 0;
    rowCursor.set(column, row + 1);
    return {
      ...node,
      position: { x: 40 + column * COLUMN_PITCH, y: 40 + row * ROW_PITCH },
    };
  });

  return { nodes, edges: graph.edges };
}
