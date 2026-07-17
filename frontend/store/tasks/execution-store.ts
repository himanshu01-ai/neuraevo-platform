import { create } from "zustand";
import {
  NODE_HEIGHT,
  NODE_WIDTH,
  ZOOM_STEP,
  clampZoom,
  graphBounds,
  type ExecutionGraph,
} from "@/services/tasks";
import type { CanvasPosition } from "@/services/workflows";

/**
 * The execution canvas's client state: how the graph is framed, and which node
 * is being inspected.
 *
 * The graph itself is *not* here. It's server state and it lives in the Query
 * cache (docs/09) — this store holds only where the user is looking at it, which
 * is exactly the split the workflow builder's canvas section makes. A refetch
 * can replace the graph without disturbing your zoom, because the two never
 * share a home.
 *
 * The geometry comes from `services/tasks/execution-graph`, which re-exports the
 * workflow builder's graph module: `store/` may not import from `features/`, and
 * this is why that module lives in `services/` in the first place.
 *
 * Nothing here executes anything. It frames a picture of a run.
 */

export interface Viewport {
  width: number;
  height: number;
}

interface ExecutionState {
  /** Which task the viewport is framed for; used to reset when it changes. */
  taskId: string | null;
  selectedNodeId: string | null;
  zoom: number;
  pan: CanvasPosition;
  viewport: Viewport;

  /** Points the canvas at a task, resetting the frame when it's a new one. */
  focusTask: (taskId: string) => void;
  selectNode: (id: string | null) => void;
  setViewport: (viewport: Viewport) => void;
  setPan: (pan: CanvasPosition) => void;
  setZoom: (zoom: number, focus?: CanvasPosition) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  zoomToFit: (graph: ExecutionGraph) => void;
  centerOnNode: (graph: ExecutionGraph, id: string) => void;
  reset: () => void;
}

const INITIAL = {
  taskId: null,
  selectedNodeId: null,
  zoom: 1,
  pan: { x: 0, y: 0 },
  viewport: { width: 0, height: 0 },
};

export const useExecutionStore = create<ExecutionState>()((set, get) => ({
  ...INITIAL,

  focusTask: (taskId) => {
    // Re-framing on every render would fight the user's zoom; only a genuinely
    // different task resets the view.
    if (get().taskId === taskId) return;
    set({ ...INITIAL, taskId });
  },

  selectNode: (id) => set({ selectedNodeId: id }),
  setViewport: (viewport) => set({ viewport }),
  setPan: (pan) => set({ pan }),

  setZoom: (zoom, focus) =>
    set((s) => {
      const next = clampZoom(zoom);
      const point = focus ?? { x: s.viewport.width / 2, y: s.viewport.height / 2 };
      // Keep the focused point still while the scale changes around it.
      const canvasX = (point.x - s.pan.x) / s.zoom;
      const canvasY = (point.y - s.pan.y) / s.zoom;
      return {
        zoom: next,
        pan: { x: point.x - canvasX * next, y: point.y - canvasY * next },
      };
    }),

  zoomIn: () => get().setZoom(get().zoom + ZOOM_STEP),
  zoomOut: () => get().setZoom(get().zoom - ZOOM_STEP),

  zoomToFit: (graph) =>
    set((s) => {
      const bounds = graphBounds(graph.nodes);
      if (!bounds || s.viewport.width === 0) return { zoom: 1, pan: { x: 0, y: 0 } };

      const padding = 48;
      const width = bounds.maxX - bounds.minX + padding * 2;
      const height = bounds.maxY - bounds.minY + padding * 2;
      const zoom = clampZoom(Math.min(s.viewport.width / width, s.viewport.height / height, 1));

      return {
        zoom,
        pan: {
          x: s.viewport.width / 2 - ((bounds.minX + bounds.maxX) / 2) * zoom,
          y: s.viewport.height / 2 - ((bounds.minY + bounds.maxY) / 2) * zoom,
        },
      };
    }),

  centerOnNode: (graph, id) =>
    set((s) => {
      const node = graph.nodes.find((n) => n.id === id);
      if (!node) return {};
      return {
        selectedNodeId: id,
        pan: {
          x: s.viewport.width / 2 - (node.position.x + NODE_WIDTH / 2) * s.zoom,
          y: s.viewport.height / 2 - (node.position.y + NODE_HEIGHT / 2) * s.zoom,
        },
      };
    }),

  reset: () => set({ ...INITIAL }),
}));
