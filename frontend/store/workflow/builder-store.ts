import { create } from "zustand";
import {
  NODE_HEIGHT,
  NODE_WIDTH,
  ZOOM_STEP,
  clampZoom,
  defaultConfig,
  edgeExists,
  graphBounds,
  snapPosition,
  wouldCycle,
  type CanvasPosition,
  type NodeConfig,
  type NodeConfigValue,
  type NodeKind,
  type WorkflowDetail,
  type WorkflowGraph,
  type WorkflowNode,
  type WorkflowSettings,
} from "@/services/workflows";

/**
 * The workflow builder's client state: the draft being edited, its undo history,
 * and the canvas viewport.
 *
 * On the "server data is never mirrored into Zustand" rule (docs/09): this holds
 * a *draft*, not a cache. The saved workflow stays in the Query cache; opening
 * the builder copies it once into an editing buffer that the user then owns —
 * the same relationship a form has with the record it edits. `hydrate` refuses
 * to overwrite a draft for a workflow already loaded, so a background refetch
 * can never discard your edits.
 *
 * It is one store rather than two because a workflow editor is one concern:
 * deleting a node has to clear the selection, and splitting document from
 * viewport would make every mutation a cross-store handshake for no gain.
 *
 * Nothing here executes anything. It edits structure.
 */

const HISTORY_LIMIT = 50;

/** Where a new node lands when added without a drop point. */
const DEFAULT_DROP: CanvasPosition = { x: 120, y: 120 };

export interface ConnectDraft {
  sourceNode: string;
  /** Live pointer position in canvas coordinates. */
  pointer: CanvasPosition;
}

export interface Viewport {
  width: number;
  height: number;
}

export interface AddNodeInput {
  kind: NodeKind;
  /** Presentation lives in `features/workflows/models`; the caller passes it in
   *  so this store stays free of icons and labels. */
  name: string;
  description: string;
  position?: CanvasPosition;
  config?: NodeConfig;
}

interface BuilderState {
  // ---- Document -----------------------------------------------------
  workflowId: string | null;
  name: string;
  description: string;
  graph: WorkflowGraph;
  settings: WorkflowSettings;
  isDirty: boolean;
  past: WorkflowGraph[];
  future: WorkflowGraph[];

  // ---- Canvas -------------------------------------------------------
  zoom: number;
  pan: CanvasPosition;
  viewport: Viewport;
  selectedNodeId: string | null;
  connecting: ConnectDraft | null;

  // ---- Panels & feedback --------------------------------------------
  /**
   * Which side panel overlays the canvas below `lg`. From `lg` up both panels
   * are permanent columns and this is ignored — which is why it starts closed:
   * a shared "open" flag would cover a phone's whole screen on first paint.
   */
  mobilePanel: "library" | "inspector" | null;
  isValidationOpen: boolean;
  /** Transient line for the status bar (rejected connection, save result). */
  notice: string | null;

  // ---- Document actions ---------------------------------------------
  hydrate: (detail: WorkflowDetail) => void;
  resetDraft: (name?: string) => void;
  loadGraph: (graph: WorkflowGraph, settings?: WorkflowSettings) => void;
  setName: (name: string) => void;
  setDescription: (description: string) => void;
  setSettings: (patch: Partial<WorkflowSettings>) => void;
  markSaved: (id: string) => void;

  // ---- Node actions --------------------------------------------------
  addNode: (input: AddNodeInput) => string;
  updateNode: (id: string, patch: Partial<Pick<WorkflowNode, "name" | "description">>) => void;
  updateNodeConfig: (id: string, key: string, value: NodeConfigValue) => void;
  beginNodeDrag: () => void;
  moveNode: (id: string, position: CanvasPosition) => void;
  endNodeDrag: (id: string) => void;
  deleteNode: (id: string) => void;
  duplicateNode: (id: string) => void;

  // ---- Edge actions --------------------------------------------------
  /** Connect two steps directly. Returns false (with a notice) if refused. */
  connectNodes: (sourceNode: string, targetNode: string) => boolean;
  startConnect: (sourceNode: string, pointer: CanvasPosition) => void;
  updateConnect: (pointer: CanvasPosition) => void;
  endConnect: (targetNode: string | null) => void;
  deleteEdge: (id: string) => void;

  // ---- Canvas actions ------------------------------------------------
  selectNode: (id: string | null) => void;
  setViewport: (viewport: Viewport) => void;
  setPan: (pan: CanvasPosition) => void;
  setZoom: (zoom: number, focus?: CanvasPosition) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  zoomToFit: () => void;
  centerOnNode: (id: string) => void;

  // ---- History -------------------------------------------------------
  undo: () => void;
  redo: () => void;

  // ---- Panels --------------------------------------------------------
  setMobilePanel: (panel: "library" | "inspector" | null) => void;
  setValidationOpen: (open: boolean) => void;
  setNotice: (notice: string | null) => void;
}

const EMPTY_GRAPH: WorkflowGraph = { nodes: [], edges: [] };

const DEFAULT_SETTINGS: WorkflowSettings = {
  executionMode: "SEQUENTIAL",
  stopOnFailure: true,
  requireApproval: false,
};

/** Deterministic id from the current nodes — no randomness, no clock. */
function nextNodeId(nodes: readonly WorkflowNode[]): string {
  const taken = new Set(nodes.map((n) => n.id));
  let n = nodes.length + 1;
  while (taken.has(`nd_${n}`)) n++;
  return `nd_${n}`;
}

/** Keeps new steps from tripping the duplicate-names rule on arrival. */
function uniqueName(nodes: readonly WorkflowNode[], base: string): string {
  const taken = new Set(nodes.map((n) => n.name.trim().toLowerCase()));
  if (!taken.has(base.trim().toLowerCase())) return base;
  let n = 2;
  while (taken.has(`${base} ${n}`.toLowerCase())) n++;
  return `${base} ${n}`;
}

const edgeId = (source: string, target: string) => `edg_${source}__${target}`;

export const useBuilderStore = create<BuilderState>()((set, get) => ({
  workflowId: null,
  name: "Untitled workflow",
  description: "",
  graph: EMPTY_GRAPH,
  settings: DEFAULT_SETTINGS,
  isDirty: false,
  past: [],
  future: [],

  zoom: 1,
  pan: { x: 0, y: 0 },
  viewport: { width: 0, height: 0 },
  selectedNodeId: null,
  connecting: null,

  mobilePanel: null,
  isValidationOpen: false,
  notice: null,

  // ---- Document ------------------------------------------------------
  hydrate: (detail) => {
    // Refuse to clobber an in-progress draft for the same workflow: a refetch
    // must never throw away edits.
    if (get().workflowId === detail.id) return;
    set({
      workflowId: detail.id,
      name: detail.name,
      description: detail.description,
      graph: detail.graph,
      settings: detail.settings,
      isDirty: false,
      past: [],
      future: [],
      selectedNodeId: null,
      connecting: null,
      notice: null,
    });
  },

  resetDraft: (name = "Untitled workflow") =>
    set({
      workflowId: null,
      name,
      description: "",
      graph: EMPTY_GRAPH,
      settings: DEFAULT_SETTINGS,
      isDirty: false,
      past: [],
      future: [],
      selectedNodeId: null,
      connecting: null,
      zoom: 1,
      pan: { x: 0, y: 0 },
      notice: null,
    }),

  loadGraph: (graph, settings) =>
    set((s) => ({
      graph,
      settings: settings ?? s.settings,
      past: [...s.past, s.graph].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
      selectedNodeId: null,
    })),

  setName: (name) => set({ name, isDirty: true }),
  setDescription: (description) => set({ description, isDirty: true }),
  setSettings: (patch) => set((s) => ({ settings: { ...s.settings, ...patch }, isDirty: true })),
  markSaved: (id) => set({ workflowId: id, isDirty: false }),

  // ---- Nodes ---------------------------------------------------------
  addNode: (input) => {
    const state = get();
    const id = nextNodeId(state.graph.nodes);
    const node: WorkflowNode = {
      id,
      kind: input.kind,
      name: uniqueName(state.graph.nodes, input.name),
      description: input.description,
      position: snapPosition(input.position ?? DEFAULT_DROP),
      // An executable step starts with the defaults its capability contract
      // declares — chiefly the action it performs — so it is added in a state
      // that means something rather than one the author has to complete before
      // it makes sense. An explicit config still wins.
      config: input.config ?? defaultConfig(input.kind),
      status: "PENDING",
    };

    set({
      graph: { nodes: [...state.graph.nodes, node], edges: state.graph.edges },
      past: [...state.past, state.graph].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
      selectedNodeId: id,
    });
    return id;
  },

  updateNode: (id, patch) =>
    set((s) => ({
      graph: {
        nodes: s.graph.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)),
        edges: s.graph.edges,
      },
      isDirty: true,
    })),

  updateNodeConfig: (id, key, value) =>
    set((s) => ({
      graph: {
        nodes: s.graph.nodes.map((n) => (n.id === id ? { ...n, config: { ...n.config, [key]: value } } : n)),
        edges: s.graph.edges,
      },
      isDirty: true,
    })),

  /** History is pushed once at drag start, not on every pointer move. */
  beginNodeDrag: () =>
    set((s) => ({ past: [...s.past, s.graph].slice(-HISTORY_LIMIT), future: [] })),

  moveNode: (id, position) =>
    set((s) => ({
      graph: {
        nodes: s.graph.nodes.map((n) => (n.id === id ? { ...n, position } : n)),
        edges: s.graph.edges,
      },
      isDirty: true,
    })),

  endNodeDrag: (id) =>
    set((s) => ({
      graph: {
        nodes: s.graph.nodes.map((n) => (n.id === id ? { ...n, position: snapPosition(n.position) } : n)),
        edges: s.graph.edges,
      },
    })),

  deleteNode: (id) =>
    set((s) => ({
      graph: {
        nodes: s.graph.nodes.filter((n) => n.id !== id),
        edges: s.graph.edges.filter((e) => e.sourceNode !== id && e.targetNode !== id),
      },
      past: [...s.past, s.graph].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
    })),

  duplicateNode: (id) => {
    const state = get();
    const source = state.graph.nodes.find((n) => n.id === id);
    if (!source) return;

    const newId = nextNodeId(state.graph.nodes);
    const copy: WorkflowNode = {
      ...source,
      id: newId,
      name: uniqueName(state.graph.nodes, `${source.name} (copy)`),
      config: { ...source.config },
      position: snapPosition({ x: source.position.x + 40, y: source.position.y + 40 }),
    };

    set({
      graph: { nodes: [...state.graph.nodes, copy], edges: state.graph.edges },
      past: [...state.past, state.graph].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
      selectedNodeId: newId,
    });
  },

  // ---- Edges ---------------------------------------------------------
  /**
   * The one place a connection is made. Both the canvas drag and the inspector's
   * select land here, so the rules that refuse a connection can't diverge.
   */
  connectNodes: (source, targetNode) => {
    const state = get();

    if (source === targetNode) {
      set({ connecting: null, notice: "A step can't depend on itself." });
      return false;
    }
    if (edgeExists(state.graph, source, targetNode)) {
      set({ connecting: null, notice: "Those steps are already connected." });
      return false;
    }
    if (wouldCycle(state.graph, source, targetNode)) {
      set({ connecting: null, notice: "That connection would create a loop, so neither step could start." });
      return false;
    }

    set({
      graph: {
        nodes: state.graph.nodes,
        edges: [...state.graph.edges, { id: edgeId(source, targetNode), sourceNode: source, targetNode }],
      },
      past: [...state.past, state.graph].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
      connecting: null,
      notice: null,
    });
    return true;
  },

  startConnect: (sourceNode, pointer) => set({ connecting: { sourceNode, pointer }, notice: null }),
  updateConnect: (pointer) =>
    set((s) => (s.connecting ? { connecting: { ...s.connecting, pointer } } : {})),

  endConnect: (targetNode) => {
    const draft = get().connecting;
    if (!draft || !targetNode) {
      set({ connecting: null });
      return;
    }
    get().connectNodes(draft.sourceNode, targetNode);
  },

  deleteEdge: (id) =>
    set((s) => ({
      graph: { nodes: s.graph.nodes, edges: s.graph.edges.filter((e) => e.id !== id) },
      past: [...s.past, s.graph].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    })),

  // ---- Canvas --------------------------------------------------------
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

  zoomToFit: () =>
    set((s) => {
      const bounds = graphBounds(s.graph.nodes);
      if (!bounds || s.viewport.width === 0) return { zoom: 1, pan: { x: 0, y: 0 } };

      const padding = 56;
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

  centerOnNode: (id) =>
    set((s) => {
      const node = s.graph.nodes.find((n) => n.id === id);
      if (!node) return {};
      return {
        selectedNodeId: id,
        pan: {
          x: s.viewport.width / 2 - (node.position.x + NODE_WIDTH / 2) * s.zoom,
          y: s.viewport.height / 2 - (node.position.y + NODE_HEIGHT / 2) * s.zoom,
        },
      };
    }),

  // ---- History -------------------------------------------------------
  undo: () =>
    set((s) => {
      const previous = s.past[s.past.length - 1];
      if (!previous) return {};
      return {
        graph: previous,
        past: s.past.slice(0, -1),
        future: [s.graph, ...s.future].slice(0, HISTORY_LIMIT),
        isDirty: true,
        selectedNodeId: previous.nodes.some((n) => n.id === s.selectedNodeId) ? s.selectedNodeId : null,
      };
    }),

  redo: () =>
    set((s) => {
      const next = s.future[0];
      if (!next) return {};
      return {
        graph: next,
        past: [...s.past, s.graph].slice(-HISTORY_LIMIT),
        future: s.future.slice(1),
        isDirty: true,
        selectedNodeId: next.nodes.some((n) => n.id === s.selectedNodeId) ? s.selectedNodeId : null,
      };
    }),

  // ---- Panels --------------------------------------------------------
  setMobilePanel: (panel) => set({ mobilePanel: panel }),
  setValidationOpen: (open) => set({ isValidationOpen: open }),
  setNotice: (notice) => set({ notice }),
}));
