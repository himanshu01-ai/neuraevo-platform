import { DEFAULT_CONFIGURATION } from "./defaults";
import {
  EMPLOYEE_PERMISSIONS,
  PERMISSION_DEFAULT_LEVEL,
  PERMISSION_REQUIRES,
  type CapabilityAvailability,
  type EmployeeActivityEvent,
  type EmployeeCapability,
  type EmployeeConfiguration,
  type EmployeeDetail,
  type EmployeePermission,
  type EmployeeTemplate,
} from "./types";

/**
 * Deterministic employee, template, and catalog definitions. Fixtures only: no
 * clock, no randomness, no network. The same roster every load, so the directory
 * is stable across reloads and reviewable without a backend.
 *
 * Statuses here are fixture facts, not claims about a running system — nothing
 * in this file observes anything. Sprint 17.7 replaces the roster wholesale.
 */

/**
 * What the platform can offer today, independent of any employee. The six
 * executable capabilities are live; the three platform grants are staged the way
 * the roadmap in CLAUDE.md stages them — approval and notification exist as
 * workflow nodes, so they preview; nothing else is promised.
 */
export const CAPABILITY_AVAILABILITY_CATALOG: Record<EmployeeCapability, CapabilityAvailability> = {
  browser: "GENERAL",
  python: "GENERAL",
  files: "GENERAL",
  email: "GENERAL",
  calendar: "GENERAL",
  github: "GENERAL",
  memory: "GENERAL",
  approval: "PREVIEW",
  notification: "PREVIEW",
};

const config = (patch: Partial<EmployeeConfiguration> = {}): EmployeeConfiguration => ({
  ...DEFAULT_CONFIGURATION,
  ...patch,
});

/**
 * Permissions for a set of granted capabilities, resolved through the shared
 * `PERMISSION_REQUIRES` / `PERMISSION_DEFAULT_LEVEL` tables so a fixture can
 * never disagree with what the adapter would produce for the same grants.
 */
function permissionsFor(capabilities: readonly EmployeeCapability[]): EmployeePermission[] {
  const held = new Set<EmployeeCapability>(capabilities);
  return EMPLOYEE_PERMISSIONS.map((id) => ({
    id,
    level: held.has(PERMISSION_REQUIRES[id]) ? PERMISSION_DEFAULT_LEVEL[id] : "BLOCKED",
  }));
}

// =====================================================================
// Templates
// =====================================================================

export const TEMPLATES: readonly EmployeeTemplate[] = [
  {
    id: "tpl_research",
    name: "Research Specialist",
    description: "Reads widely, keeps what matters, and comes back with a brief.",
    category: "Research",
    role: "RESEARCH_ASSISTANT",
    accent: "violet",
    glyph: "brain",
    capabilities: ["browser", "files", "memory"],
    behaviorSummary:
      "Works from a question, gathers sources before answering, and cites what it used. Stores findings so the next question starts warmer.",
    configuration: config({ tone: "professional", autonomy: "balanced" }),
  },
  {
    id: "tpl_developer",
    name: "Developer",
    description: "Reads the repository, writes the change, opens the pull request.",
    category: "Engineering",
    role: "SOFTWARE_ENGINEER",
    accent: "blue",
    glyph: "code",
    capabilities: ["github", "python", "files", "browser", "approval"],
    behaviorSummary:
      "Reads before it writes. Keeps changes small and single-purpose, and asks for a review rather than merging on its own.",
    configuration: config({ tone: "concise", autonomy: "ask", executionMode: "SEQUENTIAL" }),
  },
  {
    id: "tpl_meeting",
    name: "Meeting Assistant",
    description: "Holds the calendar, preps the room, and writes up what was decided.",
    category: "Productivity",
    role: "PROJECT_MANAGER",
    accent: "amber",
    glyph: "briefcase",
    capabilities: ["calendar", "email", "memory", "notification"],
    behaviorSummary:
      "Protects focus time, brings context to every meeting, and turns decisions into follow-ups nobody has to chase.",
    configuration: config({ tone: "friendly", executionMode: "PARALLEL" }),
  },
  {
    id: "tpl_marketing",
    name: "Marketing Assistant",
    description: "Drafts the copy, checks the market, keeps the voice consistent.",
    category: "Marketing",
    role: "CONTENT_WRITER",
    accent: "rose",
    glyph: "pen",
    capabilities: ["browser", "files", "email", "memory"],
    behaviorSummary:
      "Learns the house voice and stays in it. Drafts freely, but never sends anything outward without a sign-off.",
    configuration: config({ tone: "friendly", autonomy: "ask" }),
  },
  {
    id: "tpl_support",
    name: "Support Agent",
    description: "Answers the inbox, remembers the customer, escalates the rest.",
    category: "Support",
    role: "CUSTOMER_SUPPORT",
    accent: "emerald",
    glyph: "headset",
    capabilities: ["email", "memory", "browser", "approval", "notification"],
    behaviorSummary:
      "Recognises a returning customer and picks up where they left off. Answers what it knows and hands over what it doesn't.",
    configuration: config({ tone: "friendly", priority: "HIGH" }),
  },
  {
    id: "tpl_documents",
    name: "Document Processor",
    description: "Takes a pile of files and gives back structure.",
    category: "Documents",
    role: "DATA_ANALYST",
    accent: "slate",
    glyph: "chart",
    capabilities: ["files", "python", "memory"],
    behaviorSummary:
      "Reads every file before summarising any of them. Shows the numbers it used, so the output can be checked.",
    configuration: config({ tone: "concise", executionMode: "PARALLEL" }),
  },
  {
    id: "tpl_blank",
    name: "Blank Employee",
    description: "Start from nothing and decide everything yourself.",
    category: "Custom",
    role: "CUSTOM",
    accent: "violet",
    glyph: "initials",
    capabilities: [],
    behaviorSummary: "",
    configuration: config({ requireApproval: true }),
  },
];

// =====================================================================
// Employees
// =====================================================================

/**
 * The starting roster. Every status and every health state appears at least
 * once, so each branch of the UI is reachable without editing fixtures.
 */
export const EMPLOYEES: readonly EmployeeDetail[] = [
  {
    id: "emp_1",
    name: "Atlas",
    role: "RESEARCH_ASSISTANT",
    customRole: "",
    description: "Answers the questions that would cost you an afternoon of reading.",
    status: "AVAILABLE",
    health: "HEALTHY",
    accent: "violet",
    glyph: "brain",
    capabilities: ["browser", "files", "memory"],
    assignedWorkflows: 2,
    lastActivity: "Finished the competitor brief",
    sequence: 7,
    behaviorSummary:
      "Works from a question, gathers sources before answering, and cites what it used. Stores findings so the next question starts warmer.",
    configuration: config({ tone: "professional" }),
    permissions: permissionsFor(["browser", "files", "memory"]),
    assignments: {
      workflows: [
        {
          workflowId: "wfl_1",
          workflowName: "Weekly competitor brief",
          priority: "MEDIUM",
          executionMode: "SEQUENTIAL",
          dependencySummary: "Runs end to end; nothing waits on another step.",
        },
        {
          workflowId: "wfl_2",
          workflowName: "Market signal digest",
          priority: "LOW",
          executionMode: "PARALLEL",
          dependencySummary: "Gathering runs in parallel, then one step summarises.",
        },
      ],
      currentTask: null,
      queue: [
        { id: "que_1_1", title: "Summarise the pricing page changes", priority: "MEDIUM", position: 1 },
        { id: "que_1_2", title: "Pull the Q3 analyst notes", priority: "LOW", position: 2 },
      ],
    },
    memory: {
      total: 128,
      categories: [
        { category: "Projects", count: 64 },
        { category: "Facts", count: 41 },
        { category: "People", count: 23 },
      ],
      latest: "The pricing page moved to per-seat billing in June.",
    },
  },
  {
    id: "emp_2",
    name: "Byte",
    role: "SOFTWARE_ENGINEER",
    customRole: "",
    description: "Reads the repository, writes the change, opens the pull request.",
    status: "WORKING",
    health: "HEALTHY",
    accent: "blue",
    glyph: "code",
    capabilities: ["github", "python", "files", "browser", "approval"],
    assignedWorkflows: 3,
    lastActivity: "Opened a pull request on neuraevo/api",
    sequence: 6,
    behaviorSummary:
      "Reads before it writes. Keeps changes small and single-purpose, and asks for a review rather than merging on its own.",
    configuration: config({ tone: "concise", autonomy: "ask", priority: "HIGH" }),
    permissions: permissionsFor(["github", "python", "files", "browser", "approval"]),
    assignments: {
      workflows: [
        {
          workflowId: "wfl_3",
          workflowName: "Triage new issues",
          priority: "HIGH",
          executionMode: "SEQUENTIAL",
          dependencySummary: "Each step waits on the one before it.",
        },
        {
          workflowId: "wfl_4",
          workflowName: "Dependency upgrade sweep",
          priority: "LOW",
          executionMode: "HYBRID",
          dependencySummary: "Checks run in parallel; the pull request waits on all of them.",
        },
        {
          workflowId: "wfl_5",
          workflowName: "Release notes draft",
          priority: "MEDIUM",
          executionMode: "SEQUENTIAL",
          dependencySummary: "Waits on the release tag before anything starts.",
        },
      ],
      currentTask: {
        id: "tsk_2_1",
        title: "Fix the flaky auth test",
        workflowName: "Triage new issues",
        status: "RUNNING",
        progress: 62,
      },
      queue: [
        { id: "que_2_1", title: "Upgrade the SDK to v5", priority: "LOW", position: 1 },
        { id: "que_2_2", title: "Draft notes for 0.18", priority: "MEDIUM", position: 2 },
        { id: "que_2_3", title: "Close the stale issues", priority: "LOW", position: 3 },
      ],
    },
    memory: {
      total: 214,
      categories: [
        { category: "Projects", count: 118 },
        { category: "Facts", count: 71 },
        { category: "Preferences", count: 25 },
      ],
      latest: "Tests live under backend/tests and run with unittest, not pytest.",
    },
  },
  {
    id: "emp_3",
    name: "Vera",
    role: "DATA_ANALYST",
    customRole: "",
    description: "Turns a spreadsheet nobody wants to open into three sentences.",
    status: "BUSY",
    health: "DEGRADED",
    accent: "slate",
    glyph: "chart",
    capabilities: ["python", "files", "memory", "notification"],
    assignedWorkflows: 2,
    lastActivity: "Queued behind a long-running analysis",
    sequence: 5,
    behaviorSummary:
      "Reads every file before summarising any of them. Shows the numbers it used, so the output can be checked.",
    configuration: config({ tone: "concise", executionMode: "PARALLEL", priority: "HIGH" }),
    permissions: permissionsFor(["python", "files", "memory", "notification"]),
    assignments: {
      workflows: [
        {
          workflowId: "wfl_6",
          workflowName: "Monthly revenue rollup",
          priority: "HIGH",
          executionMode: "PARALLEL",
          dependencySummary: "Each source loads independently, then one step joins them.",
        },
        {
          workflowId: "wfl_7",
          workflowName: "Churn cohort refresh",
          priority: "MEDIUM",
          executionMode: "SEQUENTIAL",
          dependencySummary: "The cohort build waits on the revenue rollup.",
        },
      ],
      currentTask: {
        id: "tsk_3_1",
        title: "Rebuild the Q3 cohort table",
        workflowName: "Churn cohort refresh",
        status: "RUNNING",
        progress: 18,
      },
      queue: [
        { id: "que_3_1", title: "Reconcile the billing export", priority: "URGENT", position: 1 },
        { id: "que_3_2", title: "Chart retention by plan", priority: "MEDIUM", position: 2 },
      ],
    },
    memory: {
      total: 76,
      categories: [
        { category: "Facts", count: 52 },
        { category: "Projects", count: 24 },
      ],
      latest: "Revenue is reported net of refunds, not gross.",
    },
  },
  {
    id: "emp_4",
    name: "Nova",
    role: "PROJECT_MANAGER",
    customRole: "",
    description: "Holds the calendar, preps the room, and writes up what was decided.",
    status: "PAUSED",
    health: "HEALTHY",
    accent: "amber",
    glyph: "briefcase",
    capabilities: ["calendar", "email", "memory", "notification"],
    assignedWorkflows: 1,
    lastActivity: "Paused by you",
    sequence: 4,
    behaviorSummary:
      "Protects focus time, brings context to every meeting, and turns decisions into follow-ups nobody has to chase.",
    configuration: config({ tone: "friendly", executionMode: "PARALLEL" }),
    permissions: permissionsFor(["calendar", "email", "memory", "notification"]),
    assignments: {
      workflows: [
        {
          workflowId: "wfl_8",
          workflowName: "Weekly planning prep",
          priority: "MEDIUM",
          executionMode: "PARALLEL",
          dependencySummary: "Agenda and notes are gathered together, then sent as one.",
        },
      ],
      currentTask: null,
      queue: [{ id: "que_4_1", title: "Prep Monday's planning agenda", priority: "MEDIUM", position: 1 }],
    },
    memory: {
      total: 91,
      categories: [
        { category: "People", count: 48 },
        { category: "Projects", count: 31 },
        { category: "Preferences", count: 12 },
      ],
      latest: "No meetings before 10am on Tuesdays.",
    },
  },
  {
    id: "emp_5",
    name: "Quill",
    role: "CONTENT_WRITER",
    customRole: "",
    description: "Drafts the copy, checks the market, keeps the voice consistent.",
    status: "OFFLINE",
    health: "UNHEALTHY",
    accent: "rose",
    glyph: "pen",
    capabilities: ["browser", "files", "memory"],
    assignedWorkflows: 0,
    lastActivity: "Went offline after a failed run",
    sequence: 3,
    behaviorSummary:
      "Learns the house voice and stays in it. Drafts freely, but never sends anything outward without a sign-off.",
    configuration: config({ tone: "friendly", autonomy: "ask", priority: "LOW" }),
    permissions: permissionsFor(["browser", "files", "memory"]),
    assignments: { workflows: [], currentTask: null, queue: [] },
    memory: {
      total: 34,
      categories: [
        { category: "Preferences", count: 21 },
        { category: "Facts", count: 13 },
      ],
      latest: "We write in sentence case, never title case.",
    },
  },
  {
    id: "emp_6",
    name: "Echo",
    role: "CUSTOMER_SUPPORT",
    customRole: "",
    description: "Answers the inbox, remembers the customer, escalates the rest.",
    status: "AVAILABLE",
    health: "HEALTHY",
    accent: "emerald",
    glyph: "headset",
    capabilities: ["email", "memory", "browser", "approval", "notification"],
    assignedWorkflows: 2,
    lastActivity: "Cleared the overnight inbox",
    sequence: 2,
    behaviorSummary:
      "Recognises a returning customer and picks up where they left off. Answers what it knows and hands over what it doesn't.",
    configuration: config({ tone: "friendly", priority: "HIGH" }),
    permissions: permissionsFor(["email", "memory", "browser", "approval", "notification"]),
    assignments: {
      workflows: [
        {
          workflowId: "wfl_9",
          workflowName: "Inbox triage",
          priority: "HIGH",
          executionMode: "SEQUENTIAL",
          dependencySummary: "Reads, recalls, then replies — strictly in order.",
        },
        {
          workflowId: "wfl_10",
          workflowName: "Escalation handoff",
          priority: "URGENT",
          executionMode: "SEQUENTIAL",
          dependencySummary: "Waits for a human decision before it notifies anyone.",
        },
      ],
      currentTask: null,
      queue: [{ id: "que_6_1", title: "Reply to the billing question from Acme", priority: "HIGH", position: 1 }],
    },
    memory: {
      total: 302,
      categories: [
        { category: "People", count: 187 },
        { category: "Facts", count: 79 },
        { category: "Projects", count: 36 },
      ],
      latest: "Acme is on the legacy annual plan and renews in March.",
    },
  },
  {
    id: "emp_7",
    name: "Sage",
    role: "SALES_ASSISTANT",
    customRole: "",
    description: "Researches the account before the call, follows up after it.",
    status: "UNKNOWN",
    health: "UNKNOWN",
    accent: "violet",
    glyph: "sparkles",
    capabilities: ["browser", "email", "calendar", "memory"],
    assignedWorkflows: 0,
    lastActivity: "Created, not yet started",
    sequence: 1,
    behaviorSummary:
      "Shows up to a call knowing the account. Follows up the same day, in the words the customer used.",
    configuration: config({ tone: "friendly", autonomy: "ask" }),
    permissions: permissionsFor(["browser", "email", "calendar", "memory"]),
    assignments: { workflows: [], currentTask: null, queue: [] },
    memory: { total: 0, categories: [], latest: null },
  },
];

// =====================================================================
// Activity
// =====================================================================

/**
 * The activity each employee has accumulated, newest first by `sequence`.
 * Fixture history — the platform is what will report real events.
 */
export const ACTIVITY: Readonly<Record<string, readonly EmployeeActivityEvent[]>> = {
  emp_1: [
    { id: "act_1_5", kind: "COMPLETED", summary: "Finished the competitor brief", sequence: 5 },
    { id: "act_1_4", kind: "ASSIGNED", summary: "Assigned to Market signal digest", sequence: 4 },
    { id: "act_1_3", kind: "CONFIGURATION_CHANGED", summary: "Tone changed to Professional", sequence: 3 },
    { id: "act_1_2", kind: "ASSIGNED", summary: "Assigned to Weekly competitor brief", sequence: 2 },
    { id: "act_1_1", kind: "CREATED", summary: "Atlas was created from Research Specialist", sequence: 1 },
  ],
  emp_2: [
    { id: "act_2_6", kind: "UPDATED", summary: "Description rewritten", sequence: 6 },
    { id: "act_2_5", kind: "ASSIGNED", summary: "Assigned to Release notes draft", sequence: 5 },
    { id: "act_2_4", kind: "COMPLETED", summary: "Opened a pull request on neuraevo/api", sequence: 4 },
    { id: "act_2_3", kind: "CONFIGURATION_CHANGED", summary: "Autonomy set to Ask first", sequence: 3 },
    { id: "act_2_2", kind: "ASSIGNED", summary: "Assigned to Triage new issues", sequence: 2 },
    { id: "act_2_1", kind: "CREATED", summary: "Byte was created from Developer", sequence: 1 },
  ],
  emp_3: [
    { id: "act_3_4", kind: "ASSIGNED", summary: "Assigned to Churn cohort refresh", sequence: 4 },
    { id: "act_3_3", kind: "CONFIGURATION_CHANGED", summary: "Execution mode set to Parallel", sequence: 3 },
    { id: "act_3_2", kind: "ASSIGNED", summary: "Assigned to Monthly revenue rollup", sequence: 2 },
    { id: "act_3_1", kind: "CREATED", summary: "Vera was created from Document Processor", sequence: 1 },
  ],
  emp_4: [
    { id: "act_4_4", kind: "PAUSED", summary: "Paused by you", sequence: 4 },
    { id: "act_4_3", kind: "RESUMED", summary: "Resumed after the calendar reconnect", sequence: 3 },
    { id: "act_4_2", kind: "ASSIGNED", summary: "Assigned to Weekly planning prep", sequence: 2 },
    { id: "act_4_1", kind: "CREATED", summary: "Nova was created from Meeting Assistant", sequence: 1 },
  ],
  emp_5: [
    { id: "act_5_3", kind: "PAUSED", summary: "Went offline after a failed run", sequence: 3 },
    { id: "act_5_2", kind: "UPDATED", summary: "Voice guidelines attached", sequence: 2 },
    { id: "act_5_1", kind: "CREATED", summary: "Quill was created from Marketing Assistant", sequence: 1 },
  ],
  emp_6: [
    { id: "act_6_5", kind: "COMPLETED", summary: "Cleared the overnight inbox", sequence: 5 },
    { id: "act_6_4", kind: "ASSIGNED", summary: "Assigned to Escalation handoff", sequence: 4 },
    { id: "act_6_3", kind: "CONFIGURATION_CHANGED", summary: "Priority raised to High", sequence: 3 },
    { id: "act_6_2", kind: "ASSIGNED", summary: "Assigned to Inbox triage", sequence: 2 },
    { id: "act_6_1", kind: "CREATED", summary: "Echo was created from Support Agent", sequence: 1 },
  ],
  emp_7: [{ id: "act_7_1", kind: "CREATED", summary: "Sage was created", sequence: 1 }],
};

/** The event a brand-new employee starts its history with. */
export const CREATED_EVENT_SUMMARY = "Created";
