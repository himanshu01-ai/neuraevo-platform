import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  NODE_HEIGHT,
  NODE_WIDTH,
  ZOOM_STEP,
  boundsOf,
  clampZoom,
  type Collection,
  type KnowledgeGraph,
} from "@/services/memory";
import type { CanvasPosition } from "@/services/workflows";

/**
 * The memory workspace's client state: what's selected, how the knowledge is
 * laid out, and how the graph is framed.
 *
 * No server data lives here (docs/09) — the knowledge stays in the Query cache
 * and this store holds only where the user is looking at it. `viewMode` is the
 * one durable preference, so it persists the way `sidebarCollapsed` does; a
 * selection is a moment, not a setting, and resets on reload.
 *
 * The graph geometry comes from `services/memory/knowledge-graph`, which
 * re-exports the workflow builder's graph module: `store/` may not import from
 * `features/`, and that is why the module lives in `services/` at all.
 *
 * Nothing here retrieves or ranks anything. It frames a picture of what's stored.
 */

export type MemoryViewMode = "grid" | "list";

/** Which section the dock below the split is showing. */
export type MemoryDockTab = "timeline" | "relationships" | "insights" | "metadata";

export interface Viewport {
  width: number;
  height: number;
}

interface MemoryState {
  selectedMemoryId: string | null;
  /** `null` means "every collection" — the tree's root. */
  selectedCollection: Collection | null;
  selectedGraphNodeId: string | null;
  viewMode: MemoryViewMode;
  dockTab: MemoryDockTab;

  // ---- Graph viewport -------------------------------------------------
  zoom: number;
  pan: CanvasPosition;
  viewport: Viewport;

  selectMemory: (id: string | null) => void;
  selectCollection: (collection: Collection | null) => void;
  selectGraphNode: (id: string | null) => void;
  setViewMode: (mode: MemoryViewMode) => void;
  setDockTab: (tab: MemoryDockTab) => void;

  setViewport: (viewport: Viewport) => void;
  setPan: (pan: CanvasPosition) => void;
  setZoom: (zoom: number, focus?: CanvasPosition) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  zoomToFit: (graph: KnowledgeGraph) => void;
  centerOnNode: (graph: KnowledgeGraph, id: string) => void;
}

export const useMemoryStore = create<MemoryState>()(
  persist(
    (set, get) => ({
      selectedMemoryId: null,
      selectedCollection: null,
      selectedGraphNodeId: null,
      viewMode: "list",
      dockTab: "timeline",

      zoom: 1,
      pan: { x: 0, y: 0 },
      viewport: { width: 0, height: 0 },

      selectMemory: (id) => set({ selectedMemoryId: id }),
      selectCollection: (selectedCollection) => set({ selectedCollection }),
      selectGraphNode: (selectedGraphNodeId) => set({ selectedGraphNodeId }),
      setViewMode: (viewMode) => set({ viewMode }),
      setDockTab: (dockTab) => set({ dockTab }),

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
          const bounds = boundsOf(graph.nodes);
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
            selectedGraphNodeId: id,
            pan: {
              x: s.viewport.width / 2 - (node.position.x + NODE_WIDTH / 2) * s.zoom,
              y: s.viewport.height / 2 - (node.position.y + NODE_HEIGHT / 2) * s.zoom,
            },
          };
        }),
    }),
    { name: "neuraevo.memory", partialize: (s) => ({ viewMode: s.viewMode }) }
  )
);
