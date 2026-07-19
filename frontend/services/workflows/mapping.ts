/**
 * Backend ⇄ frontend translation for workflows (Sprint 18.4).
 *
 * The one place the FastAPI vocabulary is spoken. Everything above the adapter
 * — hooks, stores, canvas — sees only the Sprint 17.5 domain model, so the
 * backend's names, casing and lifecycle never leak into a component.
 *
 * Four differences are reconciled here, each deliberate:
 *
 * 1. **Status.** The backend tracks an authoring lifecycle
 *    (`draft`/`published`/`archived`). Sprint 18.5 gave the frontend a matching
 *    `WorkflowLifecycle` vocabulary (`DRAFT`/`PUBLISHED`/`ARCHIVED`), so the
 *    mapping is now 1:1 and lossless — it only reconciles casing. This replaced
 *    the Sprint 18.4 fudge that squeezed the lifecycle into the unrelated
 *    execution-readiness enum. See `LIFECYCLE_TO_FRONTEND`.
 *
 * 2. **Edge field names.** The frontend edge is `sourceNode`/`targetNode`; the
 *    backend validator requires `source`/`target` and rejects anything else as
 *    a dangling edge. Renamed in both directions.
 *
 * 3. **Settings.** The backend has no settings column. They are carried inside
 *    the stored graph document alongside `nodes`/`edges` — the backend
 *    validates those two keys and preserves the rest untouched, so this is
 *    real persistence within the documented contract, not a fallback. It is
 *    still a mismatch: a `settings` column is the right long-term home.
 *
 * 4. **Sequence.** The frontend orders by an ordinal `sequence`; the backend
 *    returns `created_at`. Derived the same way the employee adapter does.
 */

import { z } from "zod";
import { EXECUTION_MODE, type ExecutionMode, type WorkflowLifecycle } from "@/types/domain";
import {
  type Sequence,
  type WorkflowDetail,
  type WorkflowDraft,
  type WorkflowEdge,
  type WorkflowGraph,
  type WorkflowNode,
  type WorkflowSettings,
  type WorkflowSummary,
} from "./types";
import { NODE_KINDS, type NodeKind } from "./types";

// =====================================================================
// Wire schemas
// =====================================================================

export const workflowSummarySchema = z.object({
  id: z.string(),
  user_id: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  status: z.string(),
  node_count: z.number(),
  archived_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string().nullable().optional(),
});

export const workflowResponseSchema = workflowSummarySchema.extend({
  // The stored document. Shape is validated structurally by the backend and
  // read defensively below — an older row may predate the settings key.
  graph: z.unknown(),
});

export type WorkflowSummaryResponse = z.infer<typeof workflowSummarySchema>;
export type WorkflowResponse = z.infer<typeof workflowResponseSchema>;

// =====================================================================
// Lifecycle
// =====================================================================

/**
 * Backend authoring status → frontend lifecycle. A 1:1 rename, casing aside:
 *
 *   draft     -> DRAFT
 *   published -> PUBLISHED
 *   archived  -> ARCHIVED
 *
 * An unrecognised value falls back to `DRAFT` — the safe, editable state — so a
 * newer backend status can't strand a workflow the UI can't act on.
 */
const LIFECYCLE_TO_FRONTEND: Record<string, WorkflowLifecycle> = {
  draft: "DRAFT",
  published: "PUBLISHED",
  archived: "ARCHIVED",
};

export function toWorkflowLifecycle(status: string): WorkflowLifecycle {
  return LIFECYCLE_TO_FRONTEND[status.trim().toLowerCase()] ?? "DRAFT";
}

/** Frontend lifecycle → the backend's lowercase authoring status. */
export function toBackendLifecycle(lifecycle: WorkflowLifecycle): string {
  return lifecycle.toLowerCase();
}

// =====================================================================
// Sequence
// =====================================================================

/**
 * An ordinal standing in for recency, derived from `created_at`.
 *
 * The frontend sorts by `sequence` (higher is newer) and never displays it, so
 * the epoch seconds of creation serve exactly as well as a counter and need no
 * extra field on the wire.
 */
export function toSequence(createdAt: string): Sequence {
  const parsed = Date.parse(createdAt);
  return Number.isNaN(parsed) ? 0 : Math.floor(parsed / 1000);
}

// =====================================================================
// Graph
// =====================================================================

const DEFAULT_SETTINGS: WorkflowSettings = {
  executionMode: "SEQUENTIAL",
  stopOnFailure: true,
  requireApproval: false,
};

const isNodeKind = (value: unknown): value is NodeKind =>
  typeof value === "string" && (NODE_KINDS as readonly string[]).includes(value);

const isExecutionMode = (value: unknown): value is ExecutionMode =>
  typeof value === "string" && (EXECUTION_MODE as readonly string[]).includes(value);

/** A record of strings, dropping anything that isn't one. */
function toConfig(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object") return {};
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).filter(
      (entry): entry is [string, string] => typeof entry[1] === "string"
    )
  );
}

function toNode(raw: unknown): WorkflowNode | null {
  if (!raw || typeof raw !== "object") return null;
  const node = raw as Record<string, unknown>;
  if (typeof node.id !== "string" || !node.id) return null;

  const position = node.position as Record<string, unknown> | undefined;

  return {
    id: node.id,
    // A kind the frontend no longer knows would break the canvas renderer, so
    // it falls back to the generic step rather than rendering nothing.
    kind: isNodeKind(node.kind) ? node.kind : "task",
    name: typeof node.name === "string" ? node.name : "",
    description: typeof node.description === "string" ? node.description : "",
    position: {
      x: typeof position?.x === "number" ? position.x : 0,
      y: typeof position?.y === "number" ? position.y : 0,
    },
    config: toConfig(node.config),
    // Authoring never stores a run status; a saved node is always PENDING.
    status: "PENDING",
  };
}

function toEdge(raw: unknown): WorkflowEdge | null {
  if (!raw || typeof raw !== "object") return null;
  const edge = raw as Record<string, unknown>;
  if (typeof edge.id !== "string" || !edge.id) return null;
  if (typeof edge.source !== "string" || typeof edge.target !== "string") return null;
  return { id: edge.id, sourceNode: edge.source, targetNode: edge.target };
}

function toSettings(raw: unknown): WorkflowSettings {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_SETTINGS };
  const settings = raw as Record<string, unknown>;
  return {
    executionMode: isExecutionMode(settings.executionMode)
      ? settings.executionMode
      : DEFAULT_SETTINGS.executionMode,
    stopOnFailure:
      typeof settings.stopOnFailure === "boolean"
        ? settings.stopOnFailure
        : DEFAULT_SETTINGS.stopOnFailure,
    requireApproval:
      typeof settings.requireApproval === "boolean"
        ? settings.requireApproval
        : DEFAULT_SETTINGS.requireApproval,
  };
}

/** The stored document → the builder's graph and settings. */
export function toGraphAndSettings(raw: unknown): {
  graph: WorkflowGraph;
  settings: WorkflowSettings;
} {
  const document = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;

  const nodes = Array.isArray(document.nodes)
    ? document.nodes.map(toNode).filter((n): n is WorkflowNode => n !== null)
    : [];
  const edges = Array.isArray(document.edges)
    ? document.edges.map(toEdge).filter((e): e is WorkflowEdge => e !== null)
    : [];

  // An edge whose endpoints didn't survive would render as a connection to
  // nothing. The backend rejects those on write, so this only guards documents
  // written by something else.
  const ids = new Set(nodes.map((n) => n.id));
  const connected = edges.filter((e) => ids.has(e.sourceNode) && ids.has(e.targetNode));

  return { graph: { nodes, edges: connected }, settings: toSettings(document.settings) };
}

/** The builder's graph and settings → the document the backend stores. */
export function toGraphDocument(
  graph: WorkflowGraph,
  settings: WorkflowSettings
): Record<string, unknown> {
  return {
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      kind: node.kind,
      name: node.name,
      description: node.description,
      position: { x: node.position.x, y: node.position.y },
      config: { ...node.config },
      // `status` is deliberately not persisted: it describes a run, and this
      // domain stores structure only.
    })),
    edges: graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.sourceNode,
      target: edge.targetNode,
    })),
    settings: { ...settings },
  };
}

// =====================================================================
// Responses
// =====================================================================

export function toWorkflowSummary(response: WorkflowSummaryResponse): WorkflowSummary {
  return {
    id: response.id,
    name: response.name,
    description: response.description ?? "",
    lifecycle: toWorkflowLifecycle(response.status),
    nodeCount: response.node_count,
    sequence: toSequence(response.created_at),
  };
}

export function toWorkflowDetail(response: WorkflowResponse): WorkflowDetail {
  const { graph, settings } = toGraphAndSettings(response.graph);
  return {
    ...toWorkflowSummary(response),
    // Trust the parsed document over the server's count: they agree, but the
    // canvas renders from `graph`, so the number beside it should come from
    // the same place.
    nodeCount: graph.nodes.length,
    graph,
    settings,
  };
}

// =====================================================================
// Requests
// =====================================================================

export function toCreatePayload(draft: WorkflowDraft): Record<string, unknown> {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    graph: toGraphDocument(draft.graph, draft.settings),
  };
}

export function toUpdatePayload(draft: WorkflowDraft): Record<string, unknown> {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    graph: toGraphDocument(draft.graph, draft.settings),
  };
}
