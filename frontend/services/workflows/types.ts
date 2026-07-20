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

/**
 * One configured value on a step.
 *
 * A string covers almost everything, but not quite: some capabilities take
 * several values for one input — the addresses an email goes to — and reject a
 * single string outright. Since Sprint 18.8 the builder writes a real list for
 * those, so nothing downstream has to guess where one value ends and the next
 * begins. Only these two shapes exist; the contracts declare which applies.
 */
export type NodeConfigValue = string | string[];

/**
 * Step configuration, keyed by the names the platform reads.
 *
 * The keys are not free-form: for an executable step they come from the
 * canonical contract in `capability-contracts.ts`, which is why a workflow built
 * here runs as built. The platform still owns interpretation.
 */
export type NodeConfig = Record<string, NodeConfigValue>;

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
  /** Where it came in the run. The graph's order is not the run's order. */
  position: number;
  /** How long it took. `null` when the platform recorded no timing. */
  durationMs: number | null;
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
  /**
   * The run's own identity (Sprint 18.10). Before this, two runs of one
   * workflow were indistinguishable once the response was gone; this is the
   * handle that fetches it back.
   */
  executionId: string;
  status: LifecycleStatus;
  completedStepCount: number;
  totalStepCount: number;
  /** The step that stopped the run, or `null` when it finished. */
  failedStepId: string | null;
  steps: WorkflowRunStep[];
  /** Why the run stopped. `null` when it completed. */
  error: string | null;
}

// =====================================================================
// Execution history (Sprint 18.10)
// =====================================================================
//
// A run outlives the request that started it. These are the shapes it is read
// back in — a summary per row of history, and a detail carrying what the
// summary leaves out.

/** How a run was started. */
export type WorkflowRunTrigger = "manual" | "retry";

/** One past run, as a history list shows it. */
export interface WorkflowRunSummary {
  id: string;
  workflowId: string;
  status: LifecycleStatus;
  /** ISO instants, as the platform recorded them. */
  startedAt: string;
  finishedAt: string;
  durationMs: number;
  totalStepCount: number;
  completedStepCount: number;
  failedStepId: string | null;
  error: string | null;
  trigger: WorkflowRunTrigger;
  /** The run this one repeats, when it is a retry. */
  retryOfId: string | null;
}

/** One structured thing the platform said about a run. */
export interface WorkflowRunLog {
  sequence: number;
  level: "info" | "warning" | "error";
  message: string;
  /** The step it concerns, when it concerns one. */
  stepId: string | null;
}

/** One past run in full: what each step did, and what was said about it. */
export interface WorkflowRunDetail extends WorkflowRunSummary {
  steps: WorkflowRunStep[];
  logs: WorkflowRunLog[];
}

/** A page of a workflow's history. */
export interface WorkflowRunPage {
  items: WorkflowRunSummary[];
  total: number;
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
  /** A workflow's past runs, newest first. */
  executions(id: string): Promise<WorkflowRunPage>;
  /** One past run in full. */
  execution(executionId: string): Promise<WorkflowRunDetail>;
  /**
   * Run the workflow again, repeating a past run.
   *
   * Creates a *new* run; the one being repeated is never altered. Rejects for
   * the same reasons `execute` does, since it is the same run being asked for.
   */
  retry(executionId: string): Promise<WorkflowRun>;
  templates(): Promise<WorkflowTemplateSummary[]>;
  template(id: string): Promise<WorkflowTemplate>;
}
