import { GRID_SIZE } from "./fixtures";
import type { CanvasPosition, WorkflowGraph, WorkflowNode } from "./types";

/**
 * Canvas geometry and pure graph queries. Everything here is a function of the
 * graph — no state, no React, no side effects — so the canvas, the minimap, the
 * builder store, and the validation rules all read the same answers.
 *
 * This sits in `services/` rather than `features/` because the Zustand store
 * needs it and `store/` may not import from `features/`. It earns its place:
 * node geometry is part of what a stored `position` means.
 *
 * Terminology follows the backend's dependency graph: an edge
 * `sourceNode -> targetNode` means the target depends on the source; roots have
 * no dependencies and leaves have no dependents.
 */

/** Node box size in canvas units. Anchors and the minimap derive from these. */
export const NODE_WIDTH = 208;
export const NODE_HEIGHT = 76;

export const ZOOM_MIN = 0.4;
export const ZOOM_MAX = 2;
export const ZOOM_STEP = 0.2;

export const snap = (value: number): number => Math.round(value / GRID_SIZE) * GRID_SIZE;

export const snapPosition = (position: CanvasPosition): CanvasPosition => ({
  x: snap(position.x),
  y: snap(position.y),
});

export const clampZoom = (zoom: number): number => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom));

/** Where a connection leaves a node. */
export const outputAnchor = (node: WorkflowNode): CanvasPosition => ({
  x: node.position.x + NODE_WIDTH,
  y: node.position.y + NODE_HEIGHT / 2,
});

/** Where a connection arrives at a node. */
export const inputAnchor = (node: WorkflowNode): CanvasPosition => ({
  x: node.position.x,
  y: node.position.y + NODE_HEIGHT / 2,
});

/** Horizontal-first cubic bezier between two anchors. */
export function connectionPath(from: CanvasPosition, to: CanvasPosition): string {
  const curve = Math.max(40, Math.abs(to.x - from.x) * 0.5);
  return `M ${from.x} ${from.y} C ${from.x + curve} ${from.y}, ${to.x - curve} ${to.y}, ${to.x} ${to.y}`;
}

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** Bounding box covering every node, or null for an empty graph. */
export function graphBounds(nodes: readonly WorkflowNode[]): Bounds | null {
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
export const dependenciesOf = (graph: WorkflowGraph, id: string): string[] =>
  graph.edges.filter((e) => e.targetNode === id).map((e) => e.sourceNode);

/** Node ids that depend on `id`. */
export const dependentsOf = (graph: WorkflowGraph, id: string): string[] =>
  graph.edges.filter((e) => e.sourceNode === id).map((e) => e.targetNode);

/** Nodes with no dependencies — where a run would start. */
export const rootNodes = (graph: WorkflowGraph): WorkflowNode[] =>
  graph.nodes.filter((n) => !graph.edges.some((e) => e.targetNode === n.id));

/** Nodes with no dependents — where a run would end. */
export const leafNodes = (graph: WorkflowGraph): WorkflowNode[] =>
  graph.nodes.filter((n) => !graph.edges.some((e) => e.sourceNode === n.id));

/** Nodes with no connections at all. */
export const isolatedNodes = (graph: WorkflowGraph): WorkflowNode[] =>
  graph.nodes.filter((n) => !graph.edges.some((e) => e.sourceNode === n.id || e.targetNode === n.id));

export const edgeExists = (graph: WorkflowGraph, source: string, target: string): boolean =>
  graph.edges.some((e) => e.sourceNode === source && e.targetNode === target);

/**
 * Can `goal` be reached from `from` by following at least one edge? Starting at
 * `from`'s dependents rather than `from` itself is what makes `canReach(x, x)`
 * mean "x sits on a cycle" instead of trivially true.
 */
function canReach(graph: WorkflowGraph, from: string, goal: string): boolean {
  const seen = new Set<string>();
  const stack = dependentsOf(graph, from);

  while (stack.length > 0) {
    const current = stack.pop();
    if (current === undefined) break;
    if (current === goal) return true;
    if (seen.has(current)) continue;
    seen.add(current);
    stack.push(...dependentsOf(graph, current));
  }
  return false;
}

/** Would connecting `source -> target` close a loop back onto the source? */
export function wouldCycle(graph: WorkflowGraph, source: string, target: string): boolean {
  if (source === target) return true;
  return canReach(graph, target, source);
}

/**
 * Does the graph already contain a cycle? Connections made in the builder are
 * guarded, so this exists for graphs that arrive from elsewhere — an import.
 */
export const hasCycle = (graph: WorkflowGraph): boolean =>
  graph.nodes.some((n) => canReach(graph, n.id, n.id));
