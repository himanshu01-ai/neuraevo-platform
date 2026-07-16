import {
  hasCycle,
  isolatedNodes,
  leafNodes,
  rootNodes,
  type WorkflowGraph,
} from "@/services/workflows";

/**
 * Workflow validation rules. Each rule is a pure read of the graph structure —
 * it reports, it never repairs, and nothing here runs a workflow.
 *
 * The backend's `PlanValidator` is the authority on plan validity. These rules
 * are the authoring-time echo of the structural checks it makes (unique nodes,
 * reachable start, no cycles) so problems surface while you build rather than
 * on submission. When the backend is wired, its verdict wins.
 */

export const VALIDATION_RULES = [
  "empty-workflow",
  "missing-start",
  "missing-output",
  "disconnected-node",
  "duplicate-names",
  "invalid-connection",
] as const;
export type ValidationRule = (typeof VALIDATION_RULES)[number];

export type ValidationSeverity = "error" | "warning";

export interface ValidationIssue {
  rule: ValidationRule;
  severity: ValidationSeverity;
  message: string;
  /** Nodes the issue points at, so the panel can select them. */
  nodeIds: string[];
}

export interface ValidationReport {
  issues: ValidationIssue[];
  errorCount: number;
  warningCount: number;
  /** Structurally sound: no errors. Readiness itself stays the backend's call. */
  isValid: boolean;
}

function emptyWorkflow(graph: WorkflowGraph): ValidationIssue[] {
  if (graph.nodes.length > 0) return [];
  return [
    {
      rule: "empty-workflow",
      severity: "error",
      message: "This workflow has no steps. Add one from the step library.",
      nodeIds: [],
    },
  ];
}

/** A run needs somewhere to start: a node nothing else depends on first. */
function missingStart(graph: WorkflowGraph): ValidationIssue[] {
  if (graph.nodes.length === 0) return [];
  if (rootNodes(graph).length > 0) return [];
  return [
    {
      rule: "missing-start",
      severity: "error",
      message: "No starting step — every step depends on another one.",
      nodeIds: [],
    },
  ];
}

/** A run needs somewhere to end, and an Output step is how a result comes back. */
function missingOutput(graph: WorkflowGraph): ValidationIssue[] {
  if (graph.nodes.length === 0) return [];
  if (graph.nodes.some((n) => n.kind === "output")) return [];
  return [
    {
      rule: "missing-output",
      severity: "warning",
      message: "No Output step, so this workflow returns nothing.",
      nodeIds: leafNodes(graph).map((n) => n.id),
    },
  ];
}

/** A node wired to nothing would never run. */
function disconnectedNode(graph: WorkflowGraph): ValidationIssue[] {
  // A single-node workflow is a start, not an orphan.
  if (graph.nodes.length < 2) return [];
  const isolated = isolatedNodes(graph);
  if (isolated.length === 0) return [];

  return [
    {
      rule: "disconnected-node",
      severity: "warning",
      message:
        isolated.length === 1
          ? `"${isolated[0]?.name}" isn't connected to anything.`
          : `${isolated.length} steps aren't connected to anything.`,
      nodeIds: isolated.map((n) => n.id),
    },
  ];
}

/** Two steps with one name make a plan ambiguous to read and to reference. */
function duplicateNames(graph: WorkflowGraph): ValidationIssue[] {
  const byName = new Map<string, string[]>();
  for (const node of graph.nodes) {
    const key = node.name.trim().toLowerCase();
    byName.set(key, [...(byName.get(key) ?? []), node.id]);
  }

  const clashes = [...byName.values()].filter((ids) => ids.length > 1);
  if (clashes.length === 0) return [];

  return [
    {
      rule: "duplicate-names",
      severity: "warning",
      message: clashes.length === 1 ? "Two steps share a name." : `${clashes.length} names are used more than once.`,
      nodeIds: clashes.flat(),
    },
  ];
}

/** Edges that point nowhere, or loop back on themselves. */
function invalidConnection(graph: WorkflowGraph): ValidationIssue[] {
  const ids = new Set(graph.nodes.map((n) => n.id));
  const dangling = graph.edges.filter((e) => !ids.has(e.sourceNode) || !ids.has(e.targetNode));
  const issues: ValidationIssue[] = [];

  if (dangling.length > 0) {
    issues.push({
      rule: "invalid-connection",
      severity: "error",
      message: `${dangling.length} connection${dangling.length === 1 ? "" : "s"} point to a step that no longer exists.`,
      nodeIds: [],
    });
  }

  if (hasCycle(graph)) {
    issues.push({
      rule: "invalid-connection",
      severity: "error",
      message: "These steps depend on each other in a loop, so none of them could start.",
      nodeIds: [],
    });
  }

  return issues;
}

const RULE_CHECKS: readonly ((graph: WorkflowGraph) => ValidationIssue[])[] = [
  emptyWorkflow,
  missingStart,
  missingOutput,
  disconnectedNode,
  duplicateNames,
  invalidConnection,
];

/** Run every rule. Order is the order rules are declared above. */
export function validateWorkflow(graph: WorkflowGraph): ValidationReport {
  const issues = RULE_CHECKS.flatMap((check) => check(graph));
  const errorCount = issues.filter((i) => i.severity === "error").length;

  return {
    issues,
    errorCount,
    warningCount: issues.length - errorCount,
    isValid: errorCount === 0,
  };
}
