import { z } from "zod";
import {
  NODE_KINDS,
  WorkflowError,
  type WorkflowDraft,
  type WorkflowGraph,
  type WorkflowSettings,
} from "@/services/workflows";
import { EXECUTION_MODE, NODE_STATUS } from "@/types/domain";

/**
 * The workflow import/export file format.
 *
 * An imported file is untrusted input, so it is validated at the boundary with
 * Zod — the same rule docs/09 sets for anything crossing into the app. Export is
 * the exact inverse, so a file round-trips.
 *
 * This is local file I/O, not a backend call: no network is involved.
 */

const FORMAT_VERSION = 1;

const positionSchema = z.object({ x: z.number().finite(), y: z.number().finite() });

const nodeSchema = z.object({
  id: z.string().min(1),
  kind: z.enum(NODE_KINDS),
  name: z.string().min(1),
  description: z.string(),
  position: positionSchema,
  config: z.record(z.string()),
  status: z.enum(NODE_STATUS),
});

const edgeSchema = z.object({
  id: z.string().min(1),
  sourceNode: z.string().min(1),
  targetNode: z.string().min(1),
});

const graphSchema = z.object({
  nodes: z.array(nodeSchema),
  edges: z.array(edgeSchema),
});

const settingsSchema = z.object({
  executionMode: z.enum(EXECUTION_MODE),
  stopOnFailure: z.boolean(),
  requireApproval: z.boolean(),
});

const fileSchema = z.object({
  version: z.literal(FORMAT_VERSION),
  name: z.string().min(1),
  description: z.string(),
  graph: graphSchema,
  settings: settingsSchema,
});

export interface WorkflowFile {
  name: string;
  description: string;
  graph: WorkflowGraph;
  settings: WorkflowSettings;
}

export function serializeWorkflow(draft: Omit<WorkflowDraft, "id">): string {
  return JSON.stringify(
    {
      version: FORMAT_VERSION,
      name: draft.name,
      description: draft.description,
      graph: draft.graph,
      settings: draft.settings,
    },
    null,
    2
  );
}

/** Parses an exported file. Throws `WorkflowError("invalid_import")` if it isn't one. */
export function parseWorkflowFile(text: string): WorkflowFile {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new WorkflowError("invalid_import", "That file isn't valid JSON.");
  }

  const result = fileSchema.safeParse(raw);
  if (!result.success) {
    throw new WorkflowError("invalid_import", "That file isn't a NeuraEvo workflow export.");
  }

  const { name, description, graph, settings } = result.data;

  // Edges that name a step the file doesn't contain would import a broken graph.
  const ids = new Set(graph.nodes.map((n) => n.id));
  const edges = graph.edges.filter((e) => ids.has(e.sourceNode) && ids.has(e.targetNode));

  return { name, description, graph: { nodes: graph.nodes, edges }, settings };
}

/** Filename for an exported workflow. Deterministic from the name. */
export function workflowFileName(name: string): string {
  const slug =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "workflow";
  return `${slug}.neuraevo.json`;
}
