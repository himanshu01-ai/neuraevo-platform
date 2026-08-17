import { COLUMN_PITCH, ROW_PITCH } from "./knowledge-graph";
import type {
  EmployeeLink,
  GraphEdge,
  GraphNode,
  GraphNodeKind,
  KnowledgeGraph,
  MemoryDetail,
  RelationshipKind,
  TimelineEvent,
} from "./types";

/**
 * Deterministic memory, graph and timeline definitions. Fixtures only: no clock,
 * no randomness, no network. The same knowledge every load, so the workspace is
 * stable across reloads and reviewable without a backend.
 *
 * Dates are fixed ISO strings in UTC, matching what the frozen API returns for
 * `created_at` (`DateTime(timezone=True)`). They are written down, never read
 * from a clock, so "1 Jul 2026" means the same thing on every machine and in
 * every test run.
 *
 * Nothing here is retrieved, embedded, or ranked. `importanceScore` is a written
 * number, not a judgement this layer made.
 */

const OWNERS: Readonly<Record<string, EmployeeLink>> = {
  emp_1: { employeeId: "emp_1", employeeName: "Atlas" },
  emp_2: { employeeId: "emp_2", employeeName: "Byte" },
  emp_3: { employeeId: "emp_3", employeeName: "Vera" },
  emp_4: { employeeId: "emp_4", employeeName: "Nova" },
  emp_6: { employeeId: "emp_6", employeeName: "Echo" },
};

export const OWNER_LIST: readonly EmployeeLink[] = Object.values(OWNERS);

/** Every tag in use, in a stable order. The Tags facet offers exactly these. */
export const TAGS: readonly string[] = [
  "pricing",
  "competitors",
  "billing",
  "onboarding",
  "release",
  "testing",
  "voice",
  "customers",
  "sla",
  "meetings",
  "architecture",
  "security",
];

const bytes = (content: string): number => content.length;

/**
 * Builds one memory. `content` is the memory itself (the backend's `content`
 * column); `sizeBytes` is measured from it rather than invented, so the size a
 * user sees is the size of what they're reading.
 */
function memory(
  input: Omit<MemoryDetail, "sizeBytes"> & { sizeBytes?: number }
): MemoryDetail {
  return { ...input, sizeBytes: input.sizeBytes ?? bytes(input.content) };
}

// =====================================================================
// Memories
// =====================================================================

/**
 * The starting knowledge. Every memory type, collection, language and status
 * appears at least once, so each branch of the UI is reachable without editing
 * fixtures.
 */
export const MEMORIES: readonly MemoryDetail[] = [
  memory({
    id: "mem_1",
    title: "Competitor A moved to per-seat pricing",
    kind: "knowledge",
    memoryType: "permanent",
    collection: "research",
    customCollection: "",
    owner: OWNERS.emp_1 as EmployeeLink,
    createdAt: "2026-06-12T09:15:00.000Z",
    updatedAt: "2026-07-02T11:40:00.000Z",
    language: "en",
    tags: ["pricing", "competitors"],
    status: "active",
    importanceScore: 0.92,
    summary: "The pricing change that reframed the whole competitive brief.",
    content:
      "Competitor A replaced its flat $99/month plan with per-seat billing at $19/user in June 2026. The change was announced quietly on the pricing page rather than in a release post. Their free tier was left untouched.",
    linkedEmployees: [OWNERS.emp_1 as EmployeeLink, OWNERS.emp_4 as EmployeeLink],
    linkedWorkflows: [
      { workflowId: "wfl_1", workflowName: "Weekly competitor brief" },
      { workflowId: "wfl_2", workflowName: "Market signal digest" },
    ],
    usage: {
      recallCount: 34,
      lastRecalledAt: "2026-07-16T08:05:00.000Z",
      note: "Recalled by every competitor brief since it was stored.",
    },
  }),
  memory({
    id: "mem_2",
    title: "Tests run with unittest, not pytest",
    kind: "procedure",
    memoryType: "permanent",
    collection: "engineering",
    customCollection: "",
    owner: OWNERS.emp_2 as EmployeeLink,
    createdAt: "2026-05-03T14:20:00.000Z",
    updatedAt: "2026-05-03T14:20:00.000Z",
    language: "en",
    tags: ["testing", "architecture"],
    status: "active",
    importanceScore: 0.88,
    summary: "How to run the backend test suite without guessing.",
    content:
      "Backend tests live under backend/tests and run with the venv's unittest, not pytest:\n\n    PYTHONPATH=. backend/.venv/Scripts/python -m unittest discover backend/tests\n\npytest is not installed and adding it is out of scope.",
    linkedEmployees: [OWNERS.emp_2 as EmployeeLink],
    linkedWorkflows: [{ workflowId: "wfl_3", workflowName: "Triage new issues" }],
    usage: {
      recallCount: 21,
      lastRecalledAt: "2026-07-15T16:30:00.000Z",
      note: "Recalled before any test run.",
    },
  }),
  memory({
    id: "mem_3",
    title: "Acme is on the legacy annual plan",
    kind: "reference",
    memoryType: "learned",
    collection: "support",
    customCollection: "",
    owner: OWNERS.emp_6 as EmployeeLink,
    createdAt: "2026-06-28T07:45:00.000Z",
    updatedAt: "2026-07-14T09:10:00.000Z",
    language: "en",
    tags: ["customers", "billing"],
    status: "active",
    importanceScore: 0.74,
    summary: "Why Acme's invoices look different from everyone else's.",
    content:
      "Acme signed before the pricing change and remains on the legacy annual plan. It renews in March. Their invoices are generated on the old billing path, which is why the line items don't match the current template.",
    linkedEmployees: [OWNERS.emp_6 as EmployeeLink, OWNERS.emp_3 as EmployeeLink],
    linkedWorkflows: [{ workflowId: "wfl_9", workflowName: "Inbox triage" }],
    usage: {
      recallCount: 48,
      lastRecalledAt: "2026-07-17T06:20:00.000Z",
      note: "Recalled whenever Acme writes in.",
    },
  }),
  memory({
    id: "mem_4",
    title: "House voice: sentence case, never title case",
    kind: "policy",
    memoryType: "permanent",
    collection: "marketing",
    customCollection: "",
    owner: OWNERS.emp_1 as EmployeeLink,
    createdAt: "2026-04-18T10:00:00.000Z",
    updatedAt: "2026-06-01T12:15:00.000Z",
    language: "en",
    tags: ["voice"],
    status: "active",
    importanceScore: 0.65,
    summary: "The one rule every draft gets checked against.",
    content:
      "We write in sentence case, never title case — headings, buttons and page titles alike. Em dashes are fine; exclamation marks are not. Never call the product 'powerful'.",
    linkedEmployees: [OWNERS.emp_1 as EmployeeLink],
    linkedWorkflows: [],
    usage: {
      recallCount: 12,
      lastRecalledAt: "2026-07-09T13:00:00.000Z",
      note: "Recalled before anything outward-facing is drafted.",
    },
  }),
  memory({
    id: "mem_5",
    title: "Q3 billing export schema",
    kind: "document",
    memoryType: "permanent",
    collection: "projects",
    customCollection: "",
    owner: OWNERS.emp_3 as EmployeeLink,
    createdAt: "2026-07-01T08:30:00.000Z",
    updatedAt: "2026-07-16T15:45:00.000Z",
    language: "en",
    tags: ["billing"],
    status: "review",
    importanceScore: 0.81,
    summary: "The export's real columns — the header row that broke the rollup.",
    content:
      "The Q3 billing export has 12 columns:\n\naccount_id, plan, seats, mrr, currency, started_on, renews_on, discount_pct, tax_region, invoice_id, status, notes\n\nThe file that failed to parse had 9 — the tax_region, invoice_id and notes columns were dropped by the upstream job.",
    linkedEmployees: [OWNERS.emp_3 as EmployeeLink],
    linkedWorkflows: [
      { workflowId: "wfl_6", workflowName: "Monthly revenue rollup" },
      { workflowId: "wfl_7", workflowName: "Churn cohort refresh" },
    ],
    usage: {
      recallCount: 9,
      lastRecalledAt: "2026-07-16T15:50:00.000Z",
      note: "Recalled by the rollup, which is currently failing on it.",
    },
  }),
  memory({
    id: "mem_6",
    title: "No meetings before 10am on Tuesdays",
    kind: "knowledge",
    memoryType: "permanent",
    collection: "personal",
    customCollection: "",
    owner: OWNERS.emp_4 as EmployeeLink,
    createdAt: "2026-03-09T16:00:00.000Z",
    updatedAt: "2026-03-09T16:00:00.000Z",
    language: "en",
    tags: ["meetings"],
    status: "active",
    importanceScore: 0.55,
    summary: "A standing preference the calendar has to respect.",
    content:
      "Himanshu keeps Tuesday mornings clear for deep work. Nothing is scheduled before 10am on a Tuesday without being asked first.",
    linkedEmployees: [OWNERS.emp_4 as EmployeeLink],
    linkedWorkflows: [{ workflowId: "wfl_8", workflowName: "Weekly planning prep" }],
    usage: {
      recallCount: 27,
      lastRecalledAt: "2026-07-14T07:00:00.000Z",
      note: "Recalled before anything is put on the calendar.",
    },
  }),
  memory({
    id: "mem_7",
    title: "Release notes template",
    kind: "template",
    memoryType: "permanent",
    collection: "engineering",
    customCollection: "",
    owner: OWNERS.emp_2 as EmployeeLink,
    createdAt: "2026-05-22T11:05:00.000Z",
    updatedAt: "2026-07-10T09:25:00.000Z",
    language: "en",
    tags: ["release"],
    status: "active",
    importanceScore: 0.6,
    summary: "The shape every release note follows.",
    content:
      "# {version}\n\n## Added\n- {feature}\n\n## Fixed\n- {fix}\n\n## Changed\n- {change}\n\nNo marketing language. Link the pull request for anything non-obvious.",
    linkedEmployees: [OWNERS.emp_2 as EmployeeLink],
    linkedWorkflows: [{ workflowId: "wfl_5", workflowName: "Release notes draft" }],
    usage: {
      recallCount: 6,
      lastRecalledAt: "2026-07-16T10:15:00.000Z",
      note: "Recalled at the start of every release draft.",
    },
  }),
  memory({
    id: "mem_8",
    title: "Support call with Beta Corp, 14 July",
    kind: "conversation",
    memoryType: "working",
    collection: "support",
    customCollection: "",
    owner: OWNERS.emp_6 as EmployeeLink,
    createdAt: "2026-07-14T13:30:00.000Z",
    updatedAt: "2026-07-14T13:30:00.000Z",
    language: "en",
    tags: ["customers", "sla"],
    status: "active",
    importanceScore: 0.35,
    summary: "What Beta Corp asked for, in their words.",
    content:
      "Beta Corp asked whether the SLA covers scheduled maintenance windows. Told them it does not, and that windows are announced a week ahead. They want it in the contract at renewal — flagged for legal.",
    linkedEmployees: [OWNERS.emp_6 as EmployeeLink],
    linkedWorkflows: [{ workflowId: "wfl_10", workflowName: "Escalation handoff" }],
    usage: {
      recallCount: 2,
      lastRecalledAt: "2026-07-15T09:00:00.000Z",
      note: "Working context for the open escalation.",
    },
  }),
  memory({
    id: "mem_9",
    title: "Onboarding funnel drop-off is at step 3",
    kind: "knowledge",
    memoryType: "learned",
    collection: "projects",
    customCollection: "",
    owner: OWNERS.emp_3 as EmployeeLink,
    createdAt: "2026-07-08T09:00:00.000Z",
    updatedAt: "2026-07-15T14:20:00.000Z",
    language: "en",
    tags: ["onboarding"],
    status: "active",
    importanceScore: 0.7,
    summary: "Where people actually give up.",
    content:
      "Across the last 400 sign-ups, 38% stop at step 3 of onboarding — the workspace-setup step. Steps 1, 2 and 4 lose under 6% each. The step asks for a team size before it asks for anything the user came for.",
    linkedEmployees: [OWNERS.emp_3 as EmployeeLink, OWNERS.emp_1 as EmployeeLink],
    linkedWorkflows: [],
    usage: {
      recallCount: 4,
      lastRecalledAt: "2026-07-16T11:30:00.000Z",
      note: "Recalled by the onboarding audit.",
    },
  }),
  memory({
    id: "mem_10",
    title: "Preisliste Q2 (Deutsch)",
    kind: "document",
    memoryType: "permanent",
    collection: "marketing",
    customCollection: "",
    owner: OWNERS.emp_1 as EmployeeLink,
    createdAt: "2026-04-02T08:00:00.000Z",
    updatedAt: "2026-04-02T08:00:00.000Z",
    language: "de",
    tags: ["pricing"],
    status: "archived",
    importanceScore: 0.2,
    summary: "Superseded by the per-seat change — kept for the record.",
    content:
      "Preisliste für das zweite Quartal 2026. Standardplan 99 € pro Monat, Jahresabonnement mit 15 % Rabatt. Diese Preisliste wurde im Juni 2026 durch die Abrechnung pro Benutzer ersetzt.",
    linkedEmployees: [OWNERS.emp_1 as EmployeeLink],
    linkedWorkflows: [],
    usage: {
      recallCount: 0,
      lastRecalledAt: null,
      note: "Archived — nothing recalls it.",
    },
  }),
  memory({
    id: "mem_11",
    title: "Politique de sécurité des accès",
    kind: "policy",
    memoryType: "permanent",
    collection: "general",
    customCollection: "",
    owner: OWNERS.emp_2 as EmployeeLink,
    createdAt: "2026-02-14T09:30:00.000Z",
    updatedAt: "2026-06-20T10:00:00.000Z",
    language: "fr",
    tags: ["security"],
    status: "active",
    importanceScore: 0.78,
    summary: "The access rule that gates every capability grant.",
    content:
      "Aucun employé IA ne reçoit d'accès en écriture sans approbation humaine explicite. Les accès en lecture sont accordés par défaut. Toute exception doit être consignée.",
    linkedEmployees: [OWNERS.emp_2 as EmployeeLink, OWNERS.emp_6 as EmployeeLink],
    linkedWorkflows: [],
    usage: {
      recallCount: 15,
      lastRecalledAt: "2026-07-12T08:45:00.000Z",
      note: "Recalled whenever a capability grant is considered.",
    },
  }),
  memory({
    id: "mem_12",
    title: "Triage report — 17 July",
    kind: "artifact",
    memoryType: "working",
    collection: "support",
    customCollection: "",
    owner: OWNERS.emp_6 as EmployeeLink,
    createdAt: "2026-07-17T06:30:00.000Z",
    updatedAt: "2026-07-17T06:30:00.000Z",
    language: "en",
    tags: ["customers"],
    status: "active",
    importanceScore: 0.3,
    summary: "What the overnight inbox run produced.",
    content:
      "22 messages read, 18 replied to, 4 escalated. Escalations: Acme (refund outside policy), Beta Corp (contract change), Gamma (duplicate charge), Delta (data export request).",
    linkedEmployees: [OWNERS.emp_6 as EmployeeLink],
    linkedWorkflows: [{ workflowId: "wfl_9", workflowName: "Inbox triage" }],
    usage: {
      recallCount: 1,
      lastRecalledAt: "2026-07-17T07:00:00.000Z",
      note: "Working output from this morning's run.",
    },
  }),
  memory({
    id: "mem_13",
    title: "Notas de la reunión de planificación",
    kind: "conversation",
    memoryType: "learned",
    collection: "projects",
    customCollection: "",
    owner: OWNERS.emp_4 as EmployeeLink,
    createdAt: "2026-07-06T15:00:00.000Z",
    updatedAt: "2026-07-06T15:00:00.000Z",
    language: "es",
    tags: ["meetings", "onboarding"],
    status: "review",
    importanceScore: 0.45,
    summary: "Decisions from the planning meeting that nobody wrote up.",
    content:
      "Se acordó priorizar el rediseño del paso 3 de onboarding antes del cierre del trimestre. Vera presentará los datos de abandono. Nova hará el seguimiento.",
    linkedEmployees: [OWNERS.emp_4 as EmployeeLink, OWNERS.emp_3 as EmployeeLink],
    linkedWorkflows: [{ workflowId: "wfl_8", workflowName: "Weekly planning prep" }],
    usage: {
      recallCount: 3,
      lastRecalledAt: "2026-07-13T09:15:00.000Z",
      note: "Recalled when the agenda is built.",
    },
  }),
  memory({
    id: "mem_14",
    title: "उत्पाद परिचय नोट्स",
    kind: "reference",
    memoryType: "learned",
    collection: "custom",
    customCollection: "Field notes",
    owner: OWNERS.emp_1 as EmployeeLink,
    createdAt: "2026-06-30T12:00:00.000Z",
    updatedAt: "2026-06-30T12:00:00.000Z",
    language: "hi",
    tags: ["onboarding"],
    status: "active",
    importanceScore: 0.4,
    summary: "Notes from a market that doesn't read the English docs.",
    content:
      "भारतीय बाज़ार में ग्राहक पहले कीमत देखते हैं, फिर सुविधाएँ। ऑनबोर्डिंग के तीसरे चरण पर टीम का आकार पूछना यहाँ और भी ज़्यादा नुकसान करता है।",
    linkedEmployees: [OWNERS.emp_1 as EmployeeLink],
    linkedWorkflows: [],
    usage: {
      recallCount: 2,
      lastRecalledAt: "2026-07-11T10:00:00.000Z",
      note: "Recalled by market research.",
    },
  }),
  memory({
    id: "mem_15",
    title: "Old escalation runbook",
    kind: "procedure",
    memoryType: "working",
    collection: "support",
    customCollection: "",
    owner: OWNERS.emp_6 as EmployeeLink,
    createdAt: "2026-01-20T11:00:00.000Z",
    updatedAt: "2026-05-11T13:30:00.000Z",
    language: "en",
    tags: ["sla", "customers"],
    status: "archived",
    importanceScore: 0.15,
    summary: "Superseded by the escalation handoff workflow.",
    content:
      "Old runbook: page the on-call engineer directly for any P1. Replaced in May 2026 by the escalation handoff workflow, which requires approval before anyone is paged.",
    linkedEmployees: [OWNERS.emp_6 as EmployeeLink],
    linkedWorkflows: [],
    usage: { recallCount: 0, lastRecalledAt: null, note: "Archived — nothing recalls it." },
  }),
];

// =====================================================================
// Knowledge graph
// =====================================================================

const at = (col: number, row: number) => ({ x: 40 + col * COLUMN_PITCH, y: 40 + row * ROW_PITCH });

function gnode(
  id: string,
  kind: GraphNodeKind,
  name: string,
  detail: string,
  col: number,
  row: number,
  memoryId: string | null = null
): GraphNode {
  return { id, kind, name, detail, position: at(col, row), memoryId };
}

const gedge = (sourceNode: string, targetNode: string, relationship: RelationshipKind): GraphEdge => ({
  id: `ged_${sourceNode}__${targetNode}`,
  sourceNode,
  targetNode,
  relationship,
});

/**
 * How the knowledge hangs together. Columns follow `layoutGraph`'s kind order —
 * collections, documents, memories, employees, workflows, tasks — so the picture
 * reads left to right from where something is filed to what uses it.
 */
export const GRAPH: KnowledgeGraph = {
  nodes: [
    gnode("gn_col_research", "collection", "Research", "Everything the team has looked up.", 0, 0),
    gnode("gn_col_eng", "collection", "Engineering", "How the system is built and run.", 0, 1),
    gnode("gn_col_support", "collection", "Support", "What customers have told us.", 0, 2),

    gnode("gn_doc_billing", "document", "Q3 billing export schema", "The export's real columns.", 1, 1, "mem_5"),
    gnode("gn_doc_prices", "document", "Preisliste Q2", "Superseded German price list.", 1, 2, "mem_10"),

    gnode("gn_mem_1", "memory", "Competitor A per-seat pricing", "The pricing change.", 2, 0, "mem_1"),
    gnode("gn_mem_2", "memory", "Tests run with unittest", "How to run the suite.", 2, 1, "mem_2"),
    gnode("gn_mem_3", "memory", "Acme legacy annual plan", "Why Acme's invoices differ.", 2, 2, "mem_3"),
    gnode("gn_mem_9", "memory", "Onboarding drop-off at step 3", "Where people give up.", 2, 3, "mem_9"),

    gnode("gn_emp_1", "employee", "Atlas", "Research Assistant.", 3, 0),
    gnode("gn_emp_2", "employee", "Byte", "Software Engineer.", 3, 1),
    gnode("gn_emp_6", "employee", "Echo", "Customer Support.", 3, 2),
    gnode("gn_emp_3", "employee", "Vera", "Data Analyst.", 3, 3),

    gnode("gn_wfl_1", "workflow", "Weekly competitor brief", "Four steps, sequential.", 4, 0),
    gnode("gn_wfl_3", "workflow", "Triage new issues", "Each step waits on the last.", 4, 1),
    gnode("gn_wfl_9", "workflow", "Inbox triage", "Reads, recalls, then replies.", 4, 2),

    gnode("gn_tsk_1", "task", "TSK-1042 Competitor pricing brief", "Running now.", 5, 0),
    gnode("gn_tsk_3", "task", "TSK-1040 Clear the overnight inbox", "Completed.", 5, 2),
  ],
  edges: [
    gedge("gn_col_research", "gn_mem_1", "CONTAINS"),
    gedge("gn_col_eng", "gn_mem_2", "CONTAINS"),
    gedge("gn_col_eng", "gn_doc_billing", "CONTAINS"),
    gedge("gn_col_support", "gn_mem_3", "CONTAINS"),

    gedge("gn_doc_billing", "gn_mem_9", "DERIVED_FROM"),
    gedge("gn_doc_prices", "gn_mem_1", "DERIVED_FROM"),

    gedge("gn_emp_1", "gn_mem_1", "OWNS"),
    gedge("gn_emp_2", "gn_mem_2", "OWNS"),
    gedge("gn_emp_6", "gn_mem_3", "OWNS"),
    gedge("gn_emp_3", "gn_mem_9", "OWNS"),

    gedge("gn_mem_1", "gn_wfl_1", "REFERENCES"),
    gedge("gn_mem_2", "gn_wfl_3", "REFERENCES"),
    gedge("gn_mem_3", "gn_wfl_9", "REFERENCES"),
    gedge("gn_mem_9", "gn_mem_1", "RELATIONSHIP"),

    gedge("gn_wfl_1", "gn_tsk_1", "LINKED"),
    gedge("gn_wfl_9", "gn_tsk_3", "LINKED"),
    gedge("gn_emp_1", "gn_tsk_1", "LINKED"),
    gedge("gn_emp_6", "gn_tsk_3", "LINKED"),
  ],
};

// =====================================================================
// Timeline
// =====================================================================

/**
 * What has happened to the knowledge, newest first. Fixture history — the
 * platform is what will report real events.
 */
export const TIMELINE: readonly TimelineEvent[] = [
  {
    id: "tl_1",
    kind: "IMPORTED",
    memoryId: "mem_12",
    memoryTitle: "Triage report — 17 July",
    summary: "Imported from this morning's inbox triage run",
    at: "2026-07-17T06:30:00.000Z",
  },
  {
    id: "tl_2",
    kind: "UPDATED",
    memoryId: "mem_5",
    memoryTitle: "Q3 billing export schema",
    summary: "Corrected after the rollup failed to parse the export",
    at: "2026-07-16T15:45:00.000Z",
  },
  {
    id: "tl_3",
    kind: "REVIEWED",
    memoryId: "mem_5",
    memoryTitle: "Q3 billing export schema",
    summary: "Flagged for review by Vera",
    at: "2026-07-16T15:40:00.000Z",
  },
  {
    id: "tl_4",
    kind: "UPDATED",
    memoryId: "mem_9",
    memoryTitle: "Onboarding funnel drop-off is at step 3",
    summary: "Refreshed with the latest 400 sign-ups",
    at: "2026-07-15T14:20:00.000Z",
  },
  {
    id: "tl_5",
    kind: "CREATED",
    memoryId: "mem_8",
    memoryTitle: "Support call with Beta Corp, 14 July",
    summary: "Stored by Echo after the call",
    at: "2026-07-14T13:30:00.000Z",
  },
  {
    id: "tl_6",
    kind: "UPDATED",
    memoryId: "mem_3",
    memoryTitle: "Acme is on the legacy annual plan",
    summary: "Renewal month corrected to March",
    at: "2026-07-14T09:10:00.000Z",
  },
  {
    id: "tl_7",
    kind: "LINKED",
    memoryId: "mem_7",
    memoryTitle: "Release notes template",
    summary: "Linked to the Release notes draft workflow",
    at: "2026-07-10T09:25:00.000Z",
  },
  {
    id: "tl_8",
    kind: "CREATED",
    memoryId: "mem_9",
    memoryTitle: "Onboarding funnel drop-off is at step 3",
    summary: "Learned from the sign-up data",
    at: "2026-07-08T09:00:00.000Z",
  },
  {
    id: "tl_9",
    kind: "CREATED",
    memoryId: "mem_13",
    memoryTitle: "Notas de la reunión de planificación",
    summary: "Stored by Nova after the planning meeting",
    at: "2026-07-06T15:00:00.000Z",
  },
  {
    id: "tl_10",
    kind: "UPDATED",
    memoryId: "mem_1",
    memoryTitle: "Competitor A moved to per-seat pricing",
    summary: "Confirmed against the live pricing page",
    at: "2026-07-02T11:40:00.000Z",
  },
  {
    id: "tl_11",
    kind: "CREATED",
    memoryId: "mem_5",
    memoryTitle: "Q3 billing export schema",
    summary: "Documented by Vera",
    at: "2026-07-01T08:30:00.000Z",
  },
  {
    id: "tl_12",
    kind: "CREATED",
    memoryId: "mem_14",
    memoryTitle: "उत्पाद परिचय नोट्स",
    summary: "Stored by Atlas from market research",
    at: "2026-06-30T12:00:00.000Z",
  },
  {
    id: "tl_13",
    kind: "CREATED",
    memoryId: "mem_3",
    memoryTitle: "Acme is on the legacy annual plan",
    summary: "Learned from a support thread",
    at: "2026-06-28T07:45:00.000Z",
  },
  {
    id: "tl_14",
    kind: "ARCHIVED",
    memoryId: "mem_15",
    memoryTitle: "Old escalation runbook",
    summary: "Archived when the escalation workflow replaced it",
    at: "2026-05-11T13:30:00.000Z",
  },
  {
    id: "tl_15",
    kind: "ARCHIVED",
    memoryId: "mem_10",
    memoryTitle: "Preisliste Q2 (Deutsch)",
    summary: "Archived after the per-seat change",
    at: "2026-06-15T09:00:00.000Z",
  },
  {
    id: "tl_16",
    kind: "CREATED",
    memoryId: "mem_1",
    memoryTitle: "Competitor A moved to per-seat pricing",
    summary: "Stored by Atlas from the competitor brief",
    at: "2026-06-12T09:15:00.000Z",
  },
];

// =====================================================================
// Collections
// =====================================================================

/** What each shelf is for. Counts are derived by the adapter, not written here. */
export const COLLECTION_DESCRIPTIONS: Readonly<Record<string, string>> = {
  general: "Things that don't belong anywhere else yet.",
  projects: "What the current work depends on knowing.",
  research: "What the team has looked up and confirmed.",
  engineering: "How the system is built, tested and run.",
  marketing: "Voice, positioning and what's been said publicly.",
  support: "What customers have told us, and what we told them.",
  personal: "Standing preferences that shape the day.",
  custom: "Shelves you named yourself.",
};
