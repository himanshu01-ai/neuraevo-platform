import type {
  NodeConfig,
  NodeKind,
  WorkflowDetail,
  WorkflowEdge,
  WorkflowGraph,
  WorkflowNode,
  WorkflowSettings,
  WorkflowTemplate,
} from "./types";

/**
 * Deterministic workflow and template definitions. Fixtures only: no clock, no
 * randomness, no network. The same graphs every load, so the canvas is stable
 * across reloads and the builder is reviewable without a backend.
 *
 * Every node ships `status: "PENDING"` — authoring never claims a run state.
 */

/** Canvas grid step. Positions are laid out on it so fixtures snap cleanly. */
export const GRID_SIZE = 20;

const COL = 280;
const ROW = 140;

const at = (col: number, row: number) => ({ x: 80 + col * COL, y: 80 + row * ROW });

function node(
  id: string,
  kind: NodeKind,
  name: string,
  description: string,
  col: number,
  row: number,
  config: NodeConfig = {}
): WorkflowNode {
  return { id, kind, name, description, position: at(col, row), config, status: "PENDING" };
}

/** `target` depends on `source` — the backend's ExecutionEdge direction. */
function edge(sourceNode: string, targetNode: string): WorkflowEdge {
  return { id: `edg_${sourceNode}__${targetNode}`, sourceNode, targetNode };
}

const DEFAULT_SETTINGS: WorkflowSettings = {
  executionMode: "SEQUENTIAL",
  stopOnFailure: true,
  requireApproval: false,
};

const chain = (ids: string[]): WorkflowEdge[] =>
  ids.slice(0, -1).map((id, i) => edge(id, ids[i + 1] as string));

// =====================================================================
// Templates
// =====================================================================

const researchGraph: WorkflowGraph = {
  nodes: [
    node("nd_res_1", "planning", "Plan the research", "Break the question into search topics.", 0, 0),
    node("nd_res_2", "browser", "Gather sources", "Collect pages that answer the question.", 1, 0, {
      query: "",
      maxResults: "10",
    }),
    node("nd_res_3", "memory", "Remember findings", "Store what was learned for later.", 2, 0, {
      category: "Projects",
    }),
    node("nd_res_4", "output", "Research brief", "Return the summarized brief.", 3, 0, { format: "Markdown" }),
  ],
  edges: chain(["nd_res_1", "nd_res_2", "nd_res_3", "nd_res_4"]),
};

const supportGraph: WorkflowGraph = {
  nodes: [
    node("nd_sup_1", "email", "Read the request", "Pick up the incoming support message.", 0, 0, {
      folder: "Support",
    }),
    node("nd_sup_2", "memory", "Recall the customer", "Look up what we know about them.", 1, 0, {
      category: "People",
    }),
    node("nd_sup_3", "task", "Draft a reply", "Compose a response to the request.", 2, 0),
    node("nd_sup_4", "approval", "Approve the reply", "Hold until a human approves.", 3, 0, {
      approver: "",
    }),
    node("nd_sup_5", "email", "Send the reply", "Deliver the approved response.", 4, 0),
    node("nd_sup_6", "output", "Ticket resolved", "Return the outcome.", 5, 0),
  ],
  edges: chain(["nd_sup_1", "nd_sup_2", "nd_sup_3", "nd_sup_4", "nd_sup_5", "nd_sup_6"]),
};

const emailGraph: WorkflowGraph = {
  nodes: [
    node("nd_eml_1", "planning", "Plan the outreach", "Decide who to contact and why.", 0, 0),
    node("nd_eml_2", "email", "Read the thread", "Load the conversation so far.", 1, 0),
    node("nd_eml_3", "condition", "Needs a follow-up?", "Branch on whether a reply is due.", 2, 0, {
      expression: "",
    }),
    node("nd_eml_4", "email", "Send follow-up", "Send the follow-up message.", 3, 0),
    node("nd_eml_5", "notification", "Tell me it went", "Notify that the message was sent.", 3, 1),
    node("nd_eml_6", "output", "Outreach done", "Return what was sent.", 4, 0),
  ],
  edges: [
    ...chain(["nd_eml_1", "nd_eml_2", "nd_eml_3", "nd_eml_4"]),
    edge("nd_eml_3", "nd_eml_5"),
    edge("nd_eml_4", "nd_eml_6"),
    edge("nd_eml_5", "nd_eml_6"),
  ],
};

const documentGraph: WorkflowGraph = {
  nodes: [
    node("nd_doc_1", "file", "Open the document", "Load the file to review.", 0, 0, { path: "" }),
    node("nd_doc_2", "python", "Extract the text", "Pull the readable content out.", 1, 0, { script: "" }),
    node("nd_doc_3", "task", "Review it", "Assess the document against the brief.", 2, 0),
    node("nd_doc_4", "approval", "Sign off", "Hold until a human signs off.", 3, 0),
    node("nd_doc_5", "output", "Review notes", "Return the review.", 4, 0),
  ],
  edges: chain(["nd_doc_1", "nd_doc_2", "nd_doc_3", "nd_doc_4", "nd_doc_5"]),
};

const meetingGraph: WorkflowGraph = {
  nodes: [
    node("nd_mtg_1", "calendar", "Read the agenda", "Load the meeting and its agenda.", 0, 0),
    node("nd_mtg_2", "task", "Prepare the brief", "Assemble what's needed beforehand.", 1, 0),
    node("nd_mtg_3", "memory", "Recall past notes", "Bring back prior context.", 1, 1, { category: "People" }),
    node("nd_mtg_4", "notification", "Send the brief", "Notify attendees.", 2, 0),
    node("nd_mtg_5", "output", "Meeting ready", "Return the prepared brief.", 3, 0),
  ],
  edges: [
    edge("nd_mtg_1", "nd_mtg_2"),
    edge("nd_mtg_1", "nd_mtg_3"),
    edge("nd_mtg_2", "nd_mtg_4"),
    edge("nd_mtg_3", "nd_mtg_4"),
    edge("nd_mtg_4", "nd_mtg_5"),
  ],
};

const dataGraph: WorkflowGraph = {
  nodes: [
    node("nd_dat_1", "file", "Load the dataset", "Read the source data.", 0, 0, { path: "" }),
    node("nd_dat_2", "python", "Clean the data", "Normalize and drop bad rows.", 1, 0, { script: "" }),
    node("nd_dat_3", "loop", "For each segment", "Repeat the analysis per segment.", 2, 0, {
      collection: "",
    }),
    node("nd_dat_4", "python", "Analyze", "Compute the figures.", 3, 0, { script: "" }),
    node("nd_dat_5", "output", "Analysis result", "Return the findings.", 4, 0),
  ],
  edges: chain(["nd_dat_1", "nd_dat_2", "nd_dat_3", "nd_dat_4", "nd_dat_5"]),
};

const codeGraph: WorkflowGraph = {
  nodes: [
    node("nd_cod_1", "github", "Fetch the change", "Load the pull request.", 0, 0, { repository: "" }),
    node("nd_cod_2", "python", "Run the checks", "Execute the test suite.", 1, 0, { script: "" }),
    node("nd_cod_3", "condition", "Checks passed?", "Branch on the result.", 2, 0, { expression: "" }),
    node("nd_cod_4", "task", "Review the diff", "Read the change and comment.", 3, 0),
    node("nd_cod_5", "notification", "Report failure", "Say which check failed.", 3, 1),
    node("nd_cod_6", "output", "Review posted", "Return the review.", 4, 0),
  ],
  edges: [
    ...chain(["nd_cod_1", "nd_cod_2", "nd_cod_3", "nd_cod_4"]),
    edge("nd_cod_3", "nd_cod_5"),
    edge("nd_cod_4", "nd_cod_6"),
    edge("nd_cod_5", "nd_cod_6"),
  ],
};

export const TEMPLATES: readonly WorkflowTemplate[] = [
  {
    id: "tpl_research",
    name: "Research Assistant",
    description: "Plan a question, gather sources, and return a brief.",
    category: "Research",
    nodeCount: researchGraph.nodes.length,
    graph: researchGraph,
    settings: DEFAULT_SETTINGS,
  },
  {
    id: "tpl_support",
    name: "Customer Support",
    description: "Read a request, draft a reply, and send it once approved.",
    category: "Support",
    nodeCount: supportGraph.nodes.length,
    graph: supportGraph,
    settings: { ...DEFAULT_SETTINGS, requireApproval: true },
  },
  {
    id: "tpl_email",
    name: "Email Automation",
    description: "Follow up on a thread when a reply is due.",
    category: "Communication",
    nodeCount: emailGraph.nodes.length,
    graph: emailGraph,
    settings: DEFAULT_SETTINGS,
  },
  {
    id: "tpl_document",
    name: "Document Review",
    description: "Read a document, review it, and route it for sign-off.",
    category: "Documents",
    nodeCount: documentGraph.nodes.length,
    graph: documentGraph,
    settings: { ...DEFAULT_SETTINGS, requireApproval: true },
  },
  {
    id: "tpl_meeting",
    name: "Meeting Assistant",
    description: "Prepare a brief from the agenda and past notes.",
    category: "Productivity",
    nodeCount: meetingGraph.nodes.length,
    graph: meetingGraph,
    settings: { ...DEFAULT_SETTINGS, executionMode: "HYBRID" },
  },
  {
    id: "tpl_data",
    name: "Data Analysis",
    description: "Clean a dataset, analyze each segment, and report.",
    category: "Analysis",
    nodeCount: dataGraph.nodes.length,
    graph: dataGraph,
    settings: DEFAULT_SETTINGS,
  },
  {
    id: "tpl_code",
    name: "Code Review",
    description: "Run checks on a pull request and post a review.",
    category: "Engineering",
    nodeCount: codeGraph.nodes.length,
    graph: codeGraph,
    settings: DEFAULT_SETTINGS,
  },
  {
    id: "tpl_blank",
    name: "Custom Blank",
    description: "Start from an empty canvas and build your own.",
    category: "Custom",
    nodeCount: 0,
    graph: { nodes: [], edges: [] },
    settings: DEFAULT_SETTINGS,
  },
];

// =====================================================================
// Saved workflows
// =====================================================================

/**
 * The seed workflow list. "Release notes digest" is deliberately imperfect —
 * it has a disconnected node and no output — so the validation panel has
 * something real to report the first time you open the builder.
 */
const digestGraph: WorkflowGraph = {
  nodes: [
    node("nd_dig_1", "github", "Fetch merged PRs", "Collect what shipped.", 0, 0, { repository: "" }),
    node("nd_dig_2", "task", "Summarize them", "Write the digest.", 1, 0),
    node("nd_dig_3", "notification", "Post the digest", "Share it with the team.", 1, 1),
  ],
  edges: [edge("nd_dig_1", "nd_dig_2")],
};

export const WORKFLOWS: readonly WorkflowDetail[] = [
  {
    id: "wfl_revenue",
    name: "Weekly revenue report",
    description: "Pull the numbers, analyze them, and send the summary.",
    lifecycle: "PUBLISHED",
    nodeCount: dataGraph.nodes.length,
    sequence: 3,
    graph: dataGraph,
    settings: DEFAULT_SETTINGS,
  },
  {
    id: "wfl_triage",
    name: "Inbox triage",
    description: "Read new mail, decide what matters, and reply.",
    lifecycle: "DRAFT",
    nodeCount: emailGraph.nodes.length,
    sequence: 2,
    graph: emailGraph,
    settings: DEFAULT_SETTINGS,
  },
  {
    id: "wfl_digest",
    name: "Release notes digest",
    description: "Summarize what shipped and post it to the team.",
    lifecycle: "ARCHIVED",
    nodeCount: digestGraph.nodes.length,
    sequence: 1,
    graph: digestGraph,
    settings: DEFAULT_SETTINGS,
  },
];

export { DEFAULT_SETTINGS };
