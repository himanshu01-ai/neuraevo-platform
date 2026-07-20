/**
 * Workflow domain contracts — provider-independent. The builder depends only on
 * these types and the `WorkflowsAdapter` interface, never on a concrete
 * provider. Sprint 17.5 ships a deterministic mock adapter; a real backend
 * adapter can be dropped in later with zero changes to callers.
 *
 * Status vocabulary is never redefined here — it comes from `types/domain.ts`,
 * which mirrors the frozen backend. The graph shape mirrors the backend's
 * dependency graph (`planning/execution_dependency_graph_models.py`): an edge
 * `sourceNode -> targetNode` means the target depends on the source.
 *
 * Nothing in this layer executes anything. It describes structure only.
 */

import type {
  ExecutionMode,
  LifecycleStatus,
  NodeStatus,
  WorkflowLifecycle,
} from "@/types/domain";

/**
 * Deterministic ordinal standing in for recency, mirroring the backend's
 * `generated_sequence`. Higher is more recent. No clock times.
 */
export type Sequence = number;

/**
 * What a step does. Six of these are platform capabilities (`Capability` in
 * types/domain.ts); the rest are platform subsystems (planning, approval,
 * notification, memory) or graph controls (condition, loop, output).
 *
 * The backend has no node-kind enum — its steps carry a `tool_name` — so this
 * is a frontend authoring vocabulary and deliberately lives here rather than in
 * types/domain.ts, which mirrors backend contracts only.
 */
export const NODE_KINDS = [
  "planning",
  "task",
  "browser",
  "python",
  "file",
  "email",
  "calendar",
  "github",
  "approval",
  "notification",
  "memory",
  "condition",
  "loop",
  "output",
] as const;
export type NodeKind = (typeof NODE_KINDS)[number];

export interface CanvasPosition {
  x: number;
  y: number;
}

/** Plain key/value step configuration. The backend owns interpretation. */
export type NodeConfig = Record<string, string>;

export interface WorkflowNode {
  id: string;
  kind: NodeKind;
  name: string;
  description: string;
  position: CanvasPosition;
  config: NodeConfig;
  /**
   * Per-node execution status. Authoring never sets this to anything but
   * PENDING — a run is the backend's to report. The field exists so a live
   * status can arrive without reshaping the node.
   */
  status: NodeStatus;
}

/** A directed dependency: `targetNode` depends on `sourceNode`. */
export interface WorkflowEdge {
  id: string;
  sourceNode: string;
  targetNode: string;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface WorkflowSettings {
  executionMode: ExecutionMode;
  /** Whether a run would stop at the first failing step. Structure only. */
  stopOnFailure: boolean;
  /** Whether a run would pause for approval nodes. Structure only. */
  requireApproval: boolean;
}

export interface WorkflowSummary {
  id: string;
  name: string;
  description: string;
  /**
   * Authoring lifecycle — draft, published, or archived. This is the only
   * status an authored workflow has; execution readiness (`WorkflowStatus`) is
   * evaluated by the platform when a run happens, which this domain never does.
   */
  lifecycle: WorkflowLifecycle;
  nodeCount: number;
  sequence: Sequence;
}

export interface WorkflowDetail extends WorkflowSummary {
  graph: WorkflowGraph;
  settings: WorkflowSettings;
}

export interface WorkflowTemplateSummary {
  id: string;
  name: string;
  description: string;
  category: string;
  nodeCount: number;
}

export interface WorkflowTemplate extends WorkflowTemplateSummary {
  graph: WorkflowGraph;
  settings: WorkflowSettings;
}

/** What the builder hands back when saving a draft. */
export interface WorkflowDraft {
  id: string;
  name: string;
  description: string;
  graph: WorkflowGraph;
  settings: WorkflowSettings;
}

// =====================================================================
// Execution (Sprint 18.7)
// =====================================================================
//
// Authoring describes structure; a *run* is what happened when the platform
// executed that structure. The two are separate shapes on purpose — a run is
// never stored on a workflow, and asking for one never changes it.
//
// No new status vocabulary is invented here. A run's outcome is a
// `LifecycleStatus` and a step's is a `NodeStatus`, both from `types/domain.ts`,
// so `StatusBadge` renders them with no new mapping.

/** One key/value a step produced, already flattened for display. */
export interface WorkflowRunOutput {
  key: string;
  value: string;
}

/** What one step did during a run. */
export interface WorkflowRunStep {
  /** The authored node's id — how a step is joined back to the graph. */
  id: string;
  /** The platform capability that ran it (`filesystem` for a File step). */
  capability: string;
  status: NodeStatus;
  outputs: WorkflowRunOutput[];
}

/**
 * The outcome of one execution.
 *
 * `status` is terminal — the platform answers a run request with a finished run,
 * so `COMPLETED` or `FAILED` is what arrives. A failed run is still a successful
 * request: it is reported here, not thrown.
 */
export interface WorkflowRun {
  workflowId: string;
  status: LifecycleStatus;
  completedStepCount: number;
  totalStepCount: number;
  /** The step that stopped the run, or `null` when it finished. */
  failedStepId: string | null;
  steps: WorkflowRunStep[];
  /** Why the run stopped. `null` when it completed. */
  error: string | null;
}

export type WorkflowErrorCode = "not_found" | "unavailable" | "invalid_import" | "unknown";

export class WorkflowError extends Error {
  code: WorkflowErrorCode;
  constructor(code: WorkflowErrorCode, message: string) {
    super(message);
    this.name = "WorkflowError";
    this.code = code;
  }
}

/** The single seam every workflow backend must implement. */
export interface WorkflowsAdapter {
  list(): Promise<WorkflowSummary[]>;
  detail(id: string): Promise<WorkflowDetail>;
  save(draft: WorkflowDraft): Promise<WorkflowDetail>;
  duplicate(id: string): Promise<WorkflowDetail>;
  /** Release a draft — make it published. */
  publish(id: string): Promise<WorkflowDetail>;
  /** Return a published workflow to draft. */
  unpublish(id: string): Promise<WorkflowDetail>;
  /** Retire a workflow without destroying it. */
  archive(id: string): Promise<WorkflowDetail>;
  /** Bring an archived workflow back to the bench. */
  restore(id: string): Promise<WorkflowDetail>;
  remove(id: string): Promise<void>;
  /**
   * Run a published workflow and report what happened.
   *
   * Resolves with a finished `WorkflowRun` — including a failed one. It rejects
   * only when the run could not be started at all (not found, not published,
   * untranslatable, unreachable), which is a different fact from a run that
   * started and failed.
   */
  execute(id: string): Promise<WorkflowRun>;
  templates(): Promise<WorkflowTemplateSummary[]>;
  template(id: string): Promise<WorkflowTemplate>;
}
