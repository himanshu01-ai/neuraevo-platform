import type { NodeStatus } from "@/types/domain";
import { COLUMN_PITCH, ROW_PITCH } from "./execution-graph";
import type {
  Approval,
  Artifact,
  ExecutionEdge,
  ExecutionGraph,
  ExecutionNode,
  ExecutionNodeKind,
  TaskDetail,
  TimelineEvent,
} from "./types";

/**
 * Deterministic task, graph, timeline, artifact and approval definitions.
 * Fixtures only: no clock, no randomness, no network. The same board every load,
 * so the monitor is stable across reloads and reviewable without a backend.
 *
 * Every status here is a fixture fact, not an observation — nothing in this file
 * runs, watches, or advances anything. Progress numbers are written down, not
 * computed, exactly as a backend would hand them over. Sprint 17.8 replaces the
 * board wholesale.
 */

const at = (col: number, row: number) => ({ x: 40 + col * COLUMN_PITCH, y: 40 + row * ROW_PITCH });

function node(
  id: string,
  kind: ExecutionNodeKind,
  name: string,
  detail: string,
  col: number,
  row: number,
  status: NodeStatus = "PENDING"
): ExecutionNode {
  return { id, kind, name, detail, position: at(col, row), status };
}

/** `target` depends on `source` — the backend's ExecutionEdge direction. */
const edge = (sourceNode: string, targetNode: string): ExecutionEdge => ({
  id: `xed_${sourceNode}__${targetNode}`,
  sourceNode,
  targetNode,
});

const chain = (ids: string[]): ExecutionEdge[] =>
  ids.slice(0, -1).map((id, i) => edge(id, ids[i + 1] as string));

// =====================================================================
// Graphs
// =====================================================================

/** A run in flight: planning and workflow done, a capability working. */
const researchGraph: ExecutionGraph = {
  nodes: [
    node("xn_r1", "planning", "Plan the brief", "Broke the question into four search topics.", 0, 1, "COMPLETED"),
    node("xn_r2", "workflow", "Weekly competitor brief", "Four steps, sequential.", 1, 1, "COMPLETED"),
    node("xn_r3", "employee", "Atlas", "Research Assistant carrying the work.", 2, 1, "COMPLETED"),
    node("xn_r4", "capability", "Browser", "Reading the pricing pages.", 3, 0, "RUNNING"),
    node("xn_r5", "capability", "Files", "Waiting on the sources.", 3, 2, "PENDING"),
    node("xn_r6", "memory", "Store findings", "Waiting to record what was learned.", 4, 1, "PENDING"),
    node("xn_r7", "notification", "Tell Himanshu", "Waiting on the brief.", 5, 0, "PENDING"),
    node("xn_r8", "result", "Research brief", "Waiting on everything above.", 5, 2, "PENDING"),
  ],
  edges: [
    ...chain(["xn_r1", "xn_r2", "xn_r3"]),
    edge("xn_r3", "xn_r4"),
    edge("xn_r3", "xn_r5"),
    edge("xn_r4", "xn_r6"),
    edge("xn_r5", "xn_r6"),
    edge("xn_r6", "xn_r7"),
    edge("xn_r6", "xn_r8"),
  ],
};

/** A run stopped on a person. */
const releaseGraph: ExecutionGraph = {
  nodes: [
    node("xn_p1", "planning", "Plan the release", "Read the diff and drafted the notes.", 0, 0, "COMPLETED"),
    node("xn_p2", "workflow", "Release notes draft", "Three steps, sequential.", 1, 0, "COMPLETED"),
    node("xn_p3", "employee", "Byte", "Software Engineer carrying the work.", 2, 0, "COMPLETED"),
    node("xn_p4", "capability", "GitHub", "Read 34 merged pull requests.", 3, 0, "COMPLETED"),
    node("xn_p5", "approval", "Publish the notes", "Waiting on your sign-off.", 4, 0, "RUNNING"),
    node("xn_p6", "notification", "Announce the release", "Waiting on approval.", 5, 0, "PENDING"),
    node("xn_p7", "result", "Release notes", "Waiting on approval.", 5, 1, "PENDING"),
  ],
  edges: [...chain(["xn_p1", "xn_p2", "xn_p3", "xn_p4", "xn_p5"]), edge("xn_p5", "xn_p6"), edge("xn_p5", "xn_p7")],
};

/** A finished run. */
const inboxGraph: ExecutionGraph = {
  nodes: [
    node("xn_i1", "planning", "Plan the triage", "Sorted the inbox by age.", 0, 0, "COMPLETED"),
    node("xn_i2", "workflow", "Inbox triage", "Reads, recalls, then replies.", 1, 0, "COMPLETED"),
    node("xn_i3", "employee", "Echo", "Customer Support carrying the work.", 2, 0, "COMPLETED"),
    node("xn_i4", "capability", "Email", "Read 22 messages, drafted 18 replies.", 3, 0, "COMPLETED"),
    node("xn_i5", "memory", "Recall the customers", "Matched 14 messages to known accounts.", 3, 1, "COMPLETED"),
    node("xn_i6", "approval", "Send the replies", "Approved by you.", 4, 0, "COMPLETED"),
    node("xn_i7", "notification", "Inbox cleared", "Told you it was done.", 5, 1, "COMPLETED"),
    node("xn_i8", "result", "Triage report", "18 replied, 4 escalated.", 5, 0, "COMPLETED"),
  ],
  edges: [
    ...chain(["xn_i1", "xn_i2", "xn_i3", "xn_i4"]),
    edge("xn_i3", "xn_i5"),
    edge("xn_i4", "xn_i6"),
    edge("xn_i5", "xn_i6"),
    edge("xn_i6", "xn_i8"),
    edge("xn_i6", "xn_i7"),
  ],
};

/** A run that failed. */
const cohortGraph: ExecutionGraph = {
  nodes: [
    node("xn_c1", "planning", "Plan the rebuild", "Chose the cohort window.", 0, 0, "COMPLETED"),
    node("xn_c2", "workflow", "Churn cohort refresh", "Two steps, sequential.", 1, 0, "COMPLETED"),
    node("xn_c3", "employee", "Vera", "Data Analyst carrying the work.", 2, 0, "COMPLETED"),
    node("xn_c4", "capability", "Python", "The billing export wouldn't parse.", 3, 0, "FAILED"),
    node("xn_c5", "memory", "Store the cohort", "Never reached.", 4, 0, "SKIPPED"),
    node("xn_c6", "result", "Cohort table", "Never reached.", 5, 0, "SKIPPED"),
  ],
  edges: chain(["xn_c1", "xn_c2", "xn_c3", "xn_c4", "xn_c5", "xn_c6"]),
};

/** A run that hasn't begun. */
const planningGraph: ExecutionGraph = {
  nodes: [
    node("xn_g1", "planning", "Plan the digest", "Working out which signals matter.", 0, 0, "RUNNING"),
    node("xn_g2", "workflow", "Market signal digest", "Waiting on the plan.", 1, 0, "PENDING"),
    node("xn_g3", "employee", "Atlas", "Research Assistant standing by.", 2, 0, "PENDING"),
    node("xn_g4", "capability", "Browser", "Waiting on the plan.", 3, 0, "PENDING"),
    node("xn_g5", "result", "Signal digest", "Waiting on everything above.", 4, 0, "PENDING"),
  ],
  edges: chain(["xn_g1", "xn_g2", "xn_g3", "xn_g4", "xn_g5"]),
};

/** A run blocked on something outside it. */
const blockedGraph: ExecutionGraph = {
  nodes: [
    node("xn_b1", "planning", "Plan the rollup", "Waiting on the revenue rollup to finish.", 0, 0, "PENDING"),
    node("xn_b2", "workflow", "Monthly revenue rollup", "Blocked.", 1, 0, "PENDING"),
    node("xn_b3", "employee", "Vera", "Data Analyst, already busy.", 2, 0, "PENDING"),
    node("xn_b4", "result", "Revenue rollup", "Blocked.", 3, 0, "PENDING"),
  ],
  edges: chain(["xn_b1", "xn_b2", "xn_b3", "xn_b4"]),
};

/** A plain queued/pending run. */
const simpleGraph = (prefix: string, workflowName: string, employeeName: string): ExecutionGraph => ({
  nodes: [
    node(`${prefix}1`, "planning", "Plan the work", "Waiting to start.", 0, 0),
    node(`${prefix}2`, "workflow", workflowName, "Waiting to start.", 1, 0),
    node(`${prefix}3`, "employee", employeeName, "Standing by.", 2, 0),
    node(`${prefix}4`, "result", "Result", "Waiting on everything above.", 3, 0),
  ],
  edges: chain([`${prefix}1`, `${prefix}2`, `${prefix}3`, `${prefix}4`]),
});

// =====================================================================
// Tasks
// =====================================================================

/**
 * The starting board. Every task state appears at least once, so each branch of
 * the UI is reachable without editing fixtures.
 */
export const TASKS: readonly TaskDetail[] = [
  {
    id: "tsk_1",
    businessId: "TSK-1042",
    name: "Competitor pricing brief",
    description: "Find out what the three closest competitors changed about pricing this quarter.",
    state: "RUNNING",
    priority: "HIGH",
    executionMode: "AUTOMATIC",
    workflow: { workflowId: "wfl_1", workflowName: "Weekly competitor brief" },
    assignee: { employeeId: "emp_1", employeeName: "Atlas" },
    progress: 62,
    queuePosition: null,
    sequence: 9,
    graph: researchGraph,
    monitor: {
      state: "RUNNING",
      health: "HEALTHY",
      progress: 62,
      completedSteps: 3,
      totalSteps: 8,
      currentNodeId: "xn_r4",
      executionPath: ["xn_r1", "xn_r2", "xn_r3", "xn_r4"],
      warnings: [
        { id: "wrn_1_1", nodeId: "xn_r4", message: "One source took three attempts to load." },
      ],
      errors: [],
    },
    result: null,
  },
  {
    id: "tsk_2",
    businessId: "TSK-1041",
    name: "Publish the 0.18 release notes",
    description: "Draft the notes from the merged pull requests and announce them once approved.",
    state: "WAITING_APPROVAL",
    priority: "MEDIUM",
    executionMode: "APPROVAL_REQUIRED",
    workflow: { workflowId: "wfl_5", workflowName: "Release notes draft" },
    assignee: { employeeId: "emp_2", employeeName: "Byte" },
    progress: 71,
    queuePosition: null,
    sequence: 8,
    graph: releaseGraph,
    monitor: {
      state: "WAITING_APPROVAL",
      health: "HEALTHY",
      progress: 71,
      completedSteps: 4,
      totalSteps: 7,
      currentNodeId: "xn_p5",
      executionPath: ["xn_p1", "xn_p2", "xn_p3", "xn_p4", "xn_p5"],
      warnings: [],
      errors: [],
    },
    result: null,
  },
  {
    id: "tsk_3",
    businessId: "TSK-1040",
    name: "Clear the overnight inbox",
    description: "Read what came in overnight, reply to what's known, escalate the rest.",
    state: "COMPLETED",
    priority: "HIGH",
    executionMode: "SCHEDULED",
    workflow: { workflowId: "wfl_9", workflowName: "Inbox triage" },
    assignee: { employeeId: "emp_6", employeeName: "Echo" },
    progress: 100,
    queuePosition: null,
    sequence: 7,
    graph: inboxGraph,
    monitor: {
      state: "COMPLETED",
      health: "HEALTHY",
      progress: 100,
      completedSteps: 8,
      totalSteps: 8,
      currentNodeId: null,
      executionPath: ["xn_i1", "xn_i2", "xn_i3", "xn_i4", "xn_i5", "xn_i6", "xn_i8", "xn_i7"],
      warnings: [],
      errors: [],
    },
    result: {
      summary: "22 messages read, 18 replied to, 4 escalated to you.",
      executionReport:
        "The run took eight steps and stopped once for approval before anything left the account. Every reply was matched to a known customer first.",
      workflowOutcome: "Inbox triage completed with every step succeeding.",
      capabilitySummary: [
        { capability: "Email", invocations: 22, outcome: "Read 22, drafted 18 replies." },
        { capability: "Memory", invocations: 14, outcome: "Matched 14 messages to known accounts." },
      ],
      generatedArtifactIds: ["art_3_1", "art_3_2", "art_3_3"],
      completionDetails: [
        { label: "Steps completed", value: "8 of 8" },
        { label: "Approvals", value: "1 approved" },
        { label: "Escalated", value: "4 messages" },
        { label: "Outcome", value: "Completed" },
      ],
    },
  },
  {
    id: "tsk_4",
    businessId: "TSK-1039",
    name: "Rebuild the Q3 churn cohort",
    description: "Refresh the cohort table from the latest billing export.",
    state: "FAILED",
    priority: "URGENT",
    executionMode: "AUTOMATIC",
    workflow: { workflowId: "wfl_7", workflowName: "Churn cohort refresh" },
    assignee: { employeeId: "emp_3", employeeName: "Vera" },
    progress: 48,
    queuePosition: null,
    sequence: 6,
    graph: cohortGraph,
    monitor: {
      state: "FAILED",
      health: "UNHEALTHY",
      progress: 48,
      completedSteps: 3,
      totalSteps: 6,
      currentNodeId: "xn_c4",
      executionPath: ["xn_c1", "xn_c2", "xn_c3", "xn_c4"],
      warnings: [{ id: "wrn_4_1", nodeId: "xn_c3", message: "Vera was already at capacity when this started." }],
      errors: [
        { id: "err_4_1", nodeId: "xn_c4", message: "The billing export has a malformed header row and wouldn't parse." },
      ],
    },
    result: {
      summary: "Stopped at the billing export. Nothing was written.",
      executionReport:
        "Three steps completed before the export failed to parse. The run stopped rather than build a cohort from partial data, and the remaining steps were skipped.",
      workflowOutcome: "Churn cohort refresh failed at step 4 of 6.",
      capabilitySummary: [{ capability: "Python", invocations: 3, outcome: "Three parse attempts, all failed." }],
      generatedArtifactIds: ["art_4_1"],
      completionDetails: [
        { label: "Steps completed", value: "3 of 6" },
        { label: "Failed at", value: "Python" },
        { label: "Written", value: "Nothing" },
        { label: "Outcome", value: "Failed" },
      ],
    },
  },
  {
    id: "tsk_5",
    businessId: "TSK-1038",
    name: "Market signal digest",
    description: "Summarise what moved in the market this week.",
    state: "PLANNING",
    priority: "LOW",
    executionMode: "AUTOMATIC",
    workflow: { workflowId: "wfl_2", workflowName: "Market signal digest" },
    assignee: { employeeId: "emp_1", employeeName: "Atlas" },
    progress: 8,
    queuePosition: null,
    sequence: 5,
    graph: planningGraph,
    monitor: {
      state: "PLANNING",
      health: "HEALTHY",
      progress: 8,
      completedSteps: 0,
      totalSteps: 5,
      currentNodeId: "xn_g1",
      executionPath: ["xn_g1"],
      warnings: [],
      errors: [],
    },
    result: null,
  },
  {
    id: "tsk_6",
    businessId: "TSK-1037",
    name: "Monthly revenue rollup",
    description: "Join every revenue source into one number for the month.",
    state: "BLOCKED",
    priority: "HIGH",
    executionMode: "SCHEDULED",
    workflow: { workflowId: "wfl_6", workflowName: "Monthly revenue rollup" },
    assignee: { employeeId: "emp_3", employeeName: "Vera" },
    progress: 0,
    queuePosition: null,
    sequence: 4,
    graph: blockedGraph,
    monitor: {
      state: "BLOCKED",
      health: "DEGRADED",
      progress: 0,
      completedSteps: 0,
      totalSteps: 4,
      currentNodeId: null,
      executionPath: [],
      warnings: [],
      errors: [
        { id: "err_6_1", nodeId: null, message: "Waiting on TSK-1039 to produce a cohort table this depends on." },
      ],
    },
    result: null,
  },
  {
    id: "tsk_7",
    businessId: "TSK-1036",
    name: "Prep Monday's planning agenda",
    description: "Pull last week's decisions and build the agenda.",
    state: "QUEUED",
    priority: "MEDIUM",
    executionMode: "SCHEDULED",
    workflow: { workflowId: "wfl_8", workflowName: "Weekly planning prep" },
    assignee: { employeeId: "emp_4", employeeName: "Nova" },
    progress: 0,
    queuePosition: 1,
    sequence: 3,
    graph: simpleGraph("xn_a", "Weekly planning prep", "Nova"),
    monitor: {
      state: "QUEUED",
      health: "HEALTHY",
      progress: 0,
      completedSteps: 0,
      totalSteps: 4,
      currentNodeId: null,
      executionPath: [],
      warnings: [],
      errors: [],
    },
    result: null,
  },
  {
    id: "tsk_8",
    businessId: "TSK-1035",
    name: "Upgrade the SDK to v5",
    description: "Bump the dependency, fix what breaks, open the pull request.",
    state: "PAUSED",
    priority: "LOW",
    executionMode: "MANUAL",
    workflow: { workflowId: "wfl_4", workflowName: "Dependency upgrade sweep" },
    assignee: { employeeId: "emp_2", employeeName: "Byte" },
    progress: 25,
    queuePosition: null,
    sequence: 2,
    graph: simpleGraph("xn_u", "Dependency upgrade sweep", "Byte"),
    monitor: {
      state: "PAUSED",
      health: "HEALTHY",
      progress: 25,
      completedSteps: 1,
      totalSteps: 4,
      currentNodeId: null,
      executionPath: ["xn_u1"],
      warnings: [{ id: "wrn_8_1", nodeId: null, message: "Paused by you before the pull request step." }],
      errors: [],
    },
    result: null,
  },
  {
    id: "tsk_9",
    businessId: "TSK-1034",
    name: "Reconcile the billing export",
    description: "Check the export against the ledger before anyone reports on it.",
    state: "PENDING",
    priority: "URGENT",
    executionMode: "MANUAL",
    workflow: null,
    assignee: null,
    progress: 0,
    queuePosition: null,
    sequence: 1,
    graph: { nodes: [], edges: [] },
    monitor: {
      state: "PENDING",
      health: "UNKNOWN",
      progress: 0,
      completedSteps: 0,
      totalSteps: 0,
      currentNodeId: null,
      executionPath: [],
      warnings: [
        { id: "wrn_9_1", nodeId: null, message: "No workflow and no employee assigned, so there's nothing to run." },
      ],
      errors: [],
    },
    result: null,
  },
  {
    id: "tsk_10",
    businessId: "TSK-1033",
    name: "Draft the Q2 retrospective",
    description: "Pull the quarter's numbers into a retrospective.",
    state: "CANCELLED",
    priority: "LOW",
    executionMode: "MANUAL",
    workflow: null,
    assignee: { employeeId: "emp_5", employeeName: "Quill" },
    progress: 0,
    queuePosition: null,
    sequence: 0,
    graph: simpleGraph("xn_q", "Unassigned", "Quill"),
    monitor: {
      state: "CANCELLED",
      health: "UNKNOWN",
      progress: 0,
      completedSteps: 0,
      totalSteps: 4,
      currentNodeId: null,
      executionPath: [],
      warnings: [],
      errors: [],
    },
    result: {
      summary: "Cancelled before it started.",
      executionReport: "The task was cancelled by you before any step ran. Nothing was reached and nothing was written.",
      workflowOutcome: "No workflow ran.",
      capabilitySummary: [],
      generatedArtifactIds: [],
      completionDetails: [
        { label: "Steps completed", value: "0 of 4" },
        { label: "Outcome", value: "Cancelled" },
      ],
    },
  },
];

// =====================================================================
// Timelines
// =====================================================================

export const TIMELINES: Readonly<Record<string, readonly TimelineEvent[]>> = {
  tsk_1: [
    { id: "tl_1_6", kind: "CAPABILITY_INVOKED", summary: "Browser opened the third pricing page", nodeId: "xn_r4", sequence: 6 },
    { id: "tl_1_5", kind: "CAPABILITY_INVOKED", summary: "Browser started reading sources", nodeId: "xn_r4", sequence: 5 },
    { id: "tl_1_4", kind: "WORKFLOW_STARTED", summary: "Weekly competitor brief started", nodeId: "xn_r2", sequence: 4 },
    { id: "tl_1_3", kind: "PLANNING_STARTED", summary: "Planning broke the question into four topics", nodeId: "xn_r1", sequence: 3 },
    { id: "tl_1_2", kind: "QUEUED", summary: "Queued behind one task", nodeId: null, sequence: 2 },
    { id: "tl_1_1", kind: "TASK_CREATED", summary: "TSK-1042 created and assigned to Atlas", nodeId: null, sequence: 1 },
  ],
  tsk_2: [
    { id: "tl_2_6", kind: "APPROVAL_REQUESTED", summary: "Approval requested before publishing", nodeId: "xn_p5", sequence: 6 },
    { id: "tl_2_5", kind: "CAPABILITY_INVOKED", summary: "GitHub read 34 merged pull requests", nodeId: "xn_p4", sequence: 5 },
    { id: "tl_2_4", kind: "WORKFLOW_STARTED", summary: "Release notes draft started", nodeId: "xn_p2", sequence: 4 },
    { id: "tl_2_3", kind: "PLANNING_STARTED", summary: "Planning read the diff", nodeId: "xn_p1", sequence: 3 },
    { id: "tl_2_2", kind: "QUEUED", summary: "Queued", nodeId: null, sequence: 2 },
    { id: "tl_2_1", kind: "TASK_CREATED", summary: "TSK-1041 created and assigned to Byte", nodeId: null, sequence: 1 },
  ],
  tsk_3: [
    { id: "tl_3_10", kind: "TASK_COMPLETED", summary: "TSK-1040 completed: 18 replied, 4 escalated", nodeId: "xn_i8", sequence: 10 },
    { id: "tl_3_9", kind: "NOTIFICATION_SENT", summary: "Told you the inbox was cleared", nodeId: "xn_i7", sequence: 9 },
    { id: "tl_3_8", kind: "APPROVAL_COMPLETED", summary: "You approved sending the replies", nodeId: "xn_i6", sequence: 8 },
    { id: "tl_3_7", kind: "APPROVAL_REQUESTED", summary: "Approval requested before sending 18 replies", nodeId: "xn_i6", sequence: 7 },
    { id: "tl_3_6", kind: "MEMORY_UPDATED", summary: "Matched 14 messages to known accounts", nodeId: "xn_i5", sequence: 6 },
    { id: "tl_3_5", kind: "CAPABILITY_INVOKED", summary: "Email read 22 messages", nodeId: "xn_i4", sequence: 5 },
    { id: "tl_3_4", kind: "WORKFLOW_STARTED", summary: "Inbox triage started", nodeId: "xn_i2", sequence: 4 },
    { id: "tl_3_3", kind: "PLANNING_STARTED", summary: "Planning sorted the inbox by age", nodeId: "xn_i1", sequence: 3 },
    { id: "tl_3_2", kind: "QUEUED", summary: "Queued on schedule", nodeId: null, sequence: 2 },
    { id: "tl_3_1", kind: "TASK_CREATED", summary: "TSK-1040 created and assigned to Echo", nodeId: null, sequence: 1 },
  ],
  tsk_4: [
    { id: "tl_4_5", kind: "CAPABILITY_INVOKED", summary: "Python failed to parse the billing export", nodeId: "xn_c4", sequence: 5 },
    { id: "tl_4_4", kind: "WORKFLOW_STARTED", summary: "Churn cohort refresh started", nodeId: "xn_c2", sequence: 4 },
    { id: "tl_4_3", kind: "PLANNING_STARTED", summary: "Planning chose the cohort window", nodeId: "xn_c1", sequence: 3 },
    { id: "tl_4_2", kind: "QUEUED", summary: "Queued", nodeId: null, sequence: 2 },
    { id: "tl_4_1", kind: "TASK_CREATED", summary: "TSK-1039 created and assigned to Vera", nodeId: null, sequence: 1 },
  ],
  tsk_5: [
    { id: "tl_5_3", kind: "PLANNING_STARTED", summary: "Planning is working out which signals matter", nodeId: "xn_g1", sequence: 3 },
    { id: "tl_5_2", kind: "QUEUED", summary: "Queued", nodeId: null, sequence: 2 },
    { id: "tl_5_1", kind: "TASK_CREATED", summary: "TSK-1038 created and assigned to Atlas", nodeId: null, sequence: 1 },
  ],
  tsk_6: [{ id: "tl_6_1", kind: "TASK_CREATED", summary: "TSK-1037 created and assigned to Vera", nodeId: null, sequence: 1 }],
  tsk_7: [
    { id: "tl_7_2", kind: "QUEUED", summary: "Queued first in line", nodeId: null, sequence: 2 },
    { id: "tl_7_1", kind: "TASK_CREATED", summary: "TSK-1036 created and assigned to Nova", nodeId: null, sequence: 1 },
  ],
  tsk_8: [
    { id: "tl_8_3", kind: "WORKFLOW_STARTED", summary: "Dependency upgrade sweep started", nodeId: "xn_u2", sequence: 3 },
    { id: "tl_8_2", kind: "QUEUED", summary: "Queued", nodeId: null, sequence: 2 },
    { id: "tl_8_1", kind: "TASK_CREATED", summary: "TSK-1035 created and assigned to Byte", nodeId: null, sequence: 1 },
  ],
  tsk_9: [{ id: "tl_9_1", kind: "TASK_CREATED", summary: "TSK-1034 created", nodeId: null, sequence: 1 }],
  tsk_10: [{ id: "tl_10_1", kind: "TASK_CREATED", summary: "TSK-1033 created and assigned to Quill", nodeId: null, sequence: 1 }],
};

// =====================================================================
// Artifacts
// =====================================================================

export const ARTIFACTS: Readonly<Record<string, readonly Artifact[]>> = {
  tsk_1: [
    {
      id: "art_1_1",
      kind: "log",
      name: "browser-session.log",
      description: "What the browser opened and in what order.",
      size: "12 KB",
      preview:
        "[1] GET competitor-a.com/pricing — 200\n[2] GET competitor-b.com/plans — 200\n[3] GET competitor-c.com/pricing — 503 (retry 1)\n[4] GET competitor-c.com/pricing — 503 (retry 2)\n[5] GET competitor-c.com/pricing — 200",
      sequence: 2,
    },
    {
      id: "art_1_2",
      kind: "document",
      name: "sources.md",
      description: "The pages gathered so far.",
      size: "3 KB",
      preview:
        "# Sources\n\n- Competitor A — per-seat, $19/user (changed from flat $99 in June)\n- Competitor B — unchanged since March\n- Competitor C — added a free tier",
      sequence: 1,
    },
  ],
  tsk_2: [
    {
      id: "art_2_1",
      kind: "document",
      name: "release-notes-0.18.md",
      description: "The notes waiting on your approval.",
      size: "8 KB",
      preview:
        "# 0.18\n\n## Added\n- Workflow templates\n- Employee capability grants\n\n## Fixed\n- Flaky auth test\n- Sidebar collapse on tablet",
      sequence: 2,
    },
    {
      id: "art_2_2",
      kind: "code",
      name: "changelog.diff",
      description: "The 34 pull requests the notes were drawn from.",
      size: "46 KB",
      preview:
        "+ feat(workflows): template gallery (#412)\n+ feat(employees): capability grants (#418)\n- fix(auth): stabilise token refresh test (#421)",
      sequence: 1,
    },
  ],
  tsk_3: [
    {
      id: "art_3_1",
      kind: "report",
      name: "triage-report.pdf",
      description: "What was answered and what was escalated.",
      size: "120 KB",
      preview: null,
      sequence: 3,
    },
    {
      id: "art_3_2",
      kind: "email",
      name: "replies.mbox",
      description: "The 18 replies that were sent.",
      size: "88 KB",
      preview:
        "To: billing@acme.example\nSubject: Re: Invoice question\n\nYou're on the legacy annual plan, which renews in March…",
      sequence: 2,
    },
    {
      id: "art_3_3",
      kind: "file",
      name: "escalations.csv",
      description: "The 4 messages handed to you.",
      size: "2 KB",
      preview: "from,subject,reason\nacme,Refund request,Outside policy\nbeta,Contract change,Needs legal",
      sequence: 1,
    },
  ],
  tsk_4: [
    {
      id: "art_4_1",
      kind: "log",
      name: "parse-failure.log",
      description: "Where the export stopped parsing.",
      size: "4 KB",
      preview:
        "Traceback (most recent call last):\n  File \"rollup.py\", line 41, in load\n    header = next(reader)\nValueError: malformed header row: expected 12 columns, found 9",
      sequence: 1,
    },
  ],
  tsk_5: [],
  tsk_6: [],
  tsk_7: [],
  tsk_8: [],
  tsk_9: [],
  tsk_10: [],
};

// =====================================================================
// Approvals
// =====================================================================

export const APPROVALS: readonly Approval[] = [
  {
    id: "apr_1",
    taskId: "tsk_2",
    taskName: "Publish the 0.18 release notes",
    title: "Publish the release notes",
    description: "Byte drafted the notes from 34 merged pull requests. Publishing announces them to everyone.",
    status: "PENDING",
    requestedBy: "Byte",
    assignedReviewer: "Himanshu",
    comment: null,
    sequence: 3,
  },
  {
    id: "apr_2",
    taskId: "tsk_3",
    taskName: "Clear the overnight inbox",
    title: "Send 18 replies",
    description: "Echo drafted replies to 18 messages it recognised. Sending puts them in customers' inboxes.",
    status: "APPROVED",
    requestedBy: "Echo",
    assignedReviewer: "Himanshu",
    comment: "Checked the first three — they read right. Send them.",
    sequence: 2,
  },
  {
    id: "apr_3",
    taskId: "tsk_4",
    taskName: "Rebuild the Q3 churn cohort",
    title: "Overwrite the cohort table",
    description: "Vera wanted to replace the existing Q3 cohort table with a rebuild from the billing export.",
    status: "REJECTED",
    requestedBy: "Vera",
    assignedReviewer: "Himanshu",
    comment: "Not until the export parses. Fix the header row first.",
    sequence: 1,
  },
];

// =====================================================================
// Queue
// =====================================================================

/**
 * The line, in the order the platform put it. Ordering is carried, not derived:
 * the UI does not decide who goes first.
 */
export const QUEUE_ORDER: readonly { taskId: string; position: number; estimatedOrder: string }[] = [
  { taskId: "tsk_7", position: 1, estimatedOrder: "Next up" },
  { taskId: "tsk_9", position: 2, estimatedOrder: "After the task ahead of it" },
  { taskId: "tsk_6", position: 3, estimatedOrder: "Blocked — won't start until TSK-1039 lands" },
];
