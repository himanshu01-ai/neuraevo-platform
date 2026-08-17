import type {
  Attachment,
  ConversationDetail,
  ConversationMessage,
  EmployeeRef,
  MessageRole,
  Suggestion,
} from "./types";

/**
 * Deterministic conversation fixtures. No randomness, no clock reads — every
 * timestamp is pinned so the same screen renders the same bytes on the server
 * and the client. Identities reuse the platform's own cast: employees
 * (`emp_*`) and workflows (`wfl_*`) match `services/tasks`, tasks (`tsk_*`)
 * match its board, memories (`mem_*`) match `services/memory` — so a reference
 * card in a thread points at a record the rest of the workspace really shows.
 */

// =====================================================================
// Cast
// =====================================================================

export const EMPLOYEES = {
  emp_1: { employeeId: "emp_1", employeeName: "Atlas", roleTitle: "Research analyst" },
  emp_2: { employeeId: "emp_2", employeeName: "Byte", roleTitle: "Engineering assistant" },
  emp_3: { employeeId: "emp_3", employeeName: "Vera", roleTitle: "Customer success" },
  emp_4: { employeeId: "emp_4", employeeName: "Nova", roleTitle: "Marketing writer" },
  emp_6: { employeeId: "emp_6", employeeName: "Echo", roleTitle: "Operations coordinator" },
} satisfies Record<string, EmployeeRef>;

export const EMPLOYEE_LIST: EmployeeRef[] = Object.values(EMPLOYEES);

/** The human in every conversation. One workspace, one owner — like the rest of the mocks. */
export const OWNER = { id: "user_1", name: "Himanshu", detail: "Workspace owner" } as const;

/** Every tag the fixtures use — the filter menus read this, never a free scan. */
export const CONVERSATION_TAGS = [
  "research",
  "pricing",
  "engineering",
  "accounts",
  "marketing",
  "operations",
  "finance",
] as const;

// =====================================================================
// Message factory — compact fixtures, plain data out
// =====================================================================

type MessageSeed = Partial<ConversationMessage> & {
  role: MessageRole;
  content: string;
  createdAt: string;
};

const makeMessages = (conversationId: string, seeds: MessageSeed[]): ConversationMessage[] =>
  seeds.map((seed, index) => ({
    id: `${conversationId}_m${index + 1}`,
    conversationId,
    channel: "text",
    kind: "text",
    readStatus: "read",
    attachments: [],
    approval: null,
    artifact: null,
    workflowRef: null,
    taskRef: null,
    memoryRef: null,
    notification: null,
    ...seed,
  }));

const doc = (id: string, name: string, size: string, preview: string | null): Attachment => ({
  id,
  kind: "document",
  name,
  size,
  preview,
});

// =====================================================================
// Threads
// =====================================================================

const MESSAGES_BY_CONVERSATION: Record<string, ConversationMessage[]> = {
  conv_1: makeMessages("conv_1", [
    {
      role: "system",
      kind: "notification",
      content: "Conversation started with Atlas.",
      notification: { tone: "neutral", headline: "Conversation started with Atlas." },
      createdAt: "2026-07-14T09:00:00Z",
    },
    {
      role: "user",
      content:
        "Atlas, I need a competitor pricing brief for the Q3 planning review. Focus on the two vendors that changed models this quarter.",
      createdAt: "2026-07-14T09:02:00Z",
    },
    {
      role: "assistant",
      content:
        "On it. I'll pull what we already hold before reaching for anything new — one of the pricing changes is captured in memory.",
      createdAt: "2026-07-14T09:03:00Z",
    },
    {
      role: "assistant",
      kind: "memory_reference",
      content: "This memory covers the per-seat move and the plan mix behind it.",
      memoryRef: { memoryId: "mem_1", title: "Competitor A moved to per-seat pricing" },
      createdAt: "2026-07-14T09:03:30Z",
    },
    {
      role: "assistant",
      kind: "workflow_reference",
      content: "The weekly competitor brief workflow already gathers the rest. I'd run it rather than re-collect by hand.",
      workflowRef: { workflowId: "wfl_1", workflowName: "Weekly competitor brief" },
      createdAt: "2026-07-14T09:04:00Z",
    },
    {
      role: "user",
      content: "Agreed — run it, and fold the memory into the summary section.",
      createdAt: "2026-07-14T09:06:00Z",
    },
    {
      role: "system",
      kind: "task_reference",
      content: "A task was created from this conversation.",
      taskRef: { taskId: "tsk_1", businessId: "TASK-1001", taskName: "Weekly competitor brief" },
      createdAt: "2026-07-14T09:06:30Z",
    },
    {
      role: "assistant",
      kind: "approval_request",
      content: "Before I include the win/loss numbers, I need a sign-off — they come from the restricted deals sheet.",
      approval: {
        approvalId: "conv_1_ap1",
        title: "Include restricted win/loss data",
        description:
          "The brief reads better with the win/loss trend, but that sheet is marked restricted. Approve to include it, reject to ship the brief without it.",
        status: "PENDING",
        comment: null,
      },
      createdAt: "2026-07-15T10:15:00Z",
    },
    {
      role: "assistant",
      kind: "artifact",
      content: "Here's the draft brief while that decision is pending.",
      artifact: {
        artifactId: "conv_1_ar1",
        kind: "report",
        name: "Q3 competitor pricing brief (draft)",
        size: "18.2 KB",
        preview:
          "Two of five tracked competitors changed pricing model this quarter. Competitor A moved to per-seat; Competitor C introduced usage tiers. Net effect on our mid-market win rate: pending the restricted data decision.",
      },
      createdAt: "2026-07-15T10:16:00Z",
    },
    {
      role: "user",
      content: "Draft reads well. Tighten the tiering section and it's ready for the review.",
      attachments: [doc("conv_1_att1", "planning-review-agenda.docx", "42.1 KB", "Q3 planning review — agenda and pre-reads.")],
      createdAt: "2026-07-16T08:40:00Z",
    },
    {
      role: "assistant",
      content: "Tightened. The tiering section now leads with the price-per-unit curve and drops the vendor history footnotes.",
      createdAt: "2026-07-16T08:42:00Z",
    },
  ]),

  conv_2: makeMessages("conv_2", [
    {
      role: "user",
      content: "Byte, where did the dependency upgrade sweep land? CI was red on Friday.",
      createdAt: "2026-07-15T11:20:00Z",
    },
    {
      role: "assistant",
      kind: "task_reference",
      content: "The sweep is tracked here — two majors are held back pending review.",
      taskRef: { taskId: "tsk_4", businessId: "TASK-1004", taskName: "Dependency upgrade sweep" },
      createdAt: "2026-07-15T11:21:00Z",
    },
    {
      role: "assistant",
      kind: "artifact",
      content: "The lockfile diff, trimmed to the packages that actually moved.",
      artifact: {
        artifactId: "conv_2_ar1",
        kind: "code",
        name: "lockfile-diff.patch",
        size: "6.4 KB",
        preview: "- query-runtime 5.1.2\n+ query-runtime 5.2.0\n- motion-core 11.0.8\n+ motion-core 11.2.1",
      },
      createdAt: "2026-07-15T11:22:00Z",
    },
    {
      role: "user",
      content: "Hold the majors. What broke CI?",
      createdAt: "2026-07-15T11:25:00Z",
    },
    {
      role: "assistant",
      kind: "memory_reference",
      content: "The runner, not the upgrades — the suite is run with unittest here, and the sweep's check step assumed pytest.",
      memoryRef: { memoryId: "mem_2", title: "Tests run with unittest, not pytest" },
      createdAt: "2026-07-15T11:26:00Z",
    },
    {
      role: "system",
      kind: "notification",
      content: "Task “Dependency upgrade sweep” moved to waiting approval.",
      notification: { tone: "warning", headline: "Dependency upgrade sweep is waiting on approval." },
      createdAt: "2026-07-16T09:05:00Z",
    },
    {
      role: "assistant",
      content: "Check step fixed and re-queued. I'll report back when the majors decision is due.",
      createdAt: "2026-07-16T09:06:00Z",
    },
  ]),

  conv_3: makeMessages("conv_3", [
    {
      role: "user",
      content: "Vera, Acme's renewal call is Thursday. What should I walk in knowing?",
      createdAt: "2026-07-13T14:00:00Z",
    },
    {
      role: "assistant",
      kind: "memory_reference",
      content: "Start here — they're still on the legacy annual plan, which shapes the whole conversation.",
      memoryRef: { memoryId: "mem_3", title: "Acme is on the legacy annual plan" },
      createdAt: "2026-07-13T14:01:00Z",
    },
    {
      role: "assistant",
      kind: "approval_request",
      content: "I drafted a renewal offer with a 12% loyalty discount. That's above my threshold, so it needs your sign-off.",
      approval: {
        approvalId: "conv_3_ap1",
        title: "Approve 12% renewal discount for Acme",
        description: "Standard ceiling is 10%. The extra 2% matches what Competitor A quoted them in March.",
        status: "APPROVED",
        comment: "Approved — worth it for a two-year term.",
      },
      createdAt: "2026-07-13T14:10:00Z",
    },
    {
      role: "assistant",
      kind: "artifact",
      content: "The renewal one-pager, updated with the approved discount.",
      artifact: {
        artifactId: "conv_3_ar1",
        kind: "document",
        name: "acme-renewal-one-pager.docx",
        size: "27.9 KB",
        preview: "Acme renewal — two-year term, 12% loyalty discount, migration off legacy annual plan in month one.",
      },
      createdAt: "2026-07-13T14:12:00Z",
    },
    {
      role: "user",
      content: "Perfect. Share this thread with the account team so they have the context.",
      createdAt: "2026-07-13T15:30:00Z",
    },
    {
      role: "system",
      kind: "notification",
      content: "Conversation shared with the account team.",
      notification: { tone: "info", headline: "Conversation shared with the account team." },
      createdAt: "2026-07-13T15:31:00Z",
    },
  ]),

  conv_4: makeMessages("conv_4", [
    {
      role: "user",
      content: "Nova, draft the launch notes for the July release. Keep the house voice in mind.",
      createdAt: "2026-07-16T10:00:00Z",
    },
    {
      role: "assistant",
      kind: "memory_reference",
      content: "House voice noted — sentence case, no exclamation marks, and the product is never “powerful”.",
      memoryRef: { memoryId: "mem_4", title: "House voice: sentence case, never title case" },
      createdAt: "2026-07-16T10:01:00Z",
    },
    {
      role: "assistant",
      kind: "workflow_reference",
      content: "I'll draft through the release notes workflow so the changelog section assembles itself.",
      workflowRef: { workflowId: "wfl_5", workflowName: "Release notes draft" },
      createdAt: "2026-07-16T10:02:00Z",
    },
    {
      role: "assistant",
      kind: "artifact",
      content: "First pass. The highlights section could use one more customer-facing line from you.",
      artifact: {
        artifactId: "conv_4_ar1",
        kind: "document",
        name: "july-launch-notes.md",
        size: "9.8 KB",
        preview: "## What's new in July\nConversations now sit alongside tasks and workflows, so you can ask for work in the same place you watch it run.",
      },
      createdAt: "2026-07-16T10:20:00Z",
    },
    {
      role: "user",
      content: "Nice. I'll add the customer line tonight.",
      createdAt: "2026-07-16T12:05:00Z",
    },
  ]),

  conv_5: makeMessages("conv_5", [
    {
      role: "user",
      content: "Echo, set up triage rules for the shared inbox before the beta opens.",
      createdAt: "2026-07-10T09:30:00Z",
    },
    {
      role: "assistant",
      kind: "workflow_reference",
      content: "Inbox triage is already wired as a workflow — I'll route beta mail through it with a new label.",
      workflowRef: { workflowId: "wfl_9", workflowName: "Inbox triage" },
      createdAt: "2026-07-10T09:31:00Z",
    },
    {
      role: "assistant",
      content: "Rules staged: product feedback to the research folder, billing to Vera's queue, everything else to the daily digest.",
      createdAt: "2026-07-10T09:40:00Z",
    },
    {
      role: "user",
      content: "That covers it. Archiving this until the beta actually opens.",
      createdAt: "2026-07-10T10:00:00Z",
    },
  ]),

  conv_6: makeMessages("conv_6", [
    {
      role: "user",
      content: "Atlas, anything in this week's market signals I should raise at standup?",
      createdAt: "2026-07-17T07:45:00Z",
    },
    {
      role: "assistant",
      kind: "workflow_reference",
      content: "This week's digest just finished — two signals worth a minute each.",
      workflowRef: { workflowId: "wfl_2", workflowName: "Market signal digest" },
      createdAt: "2026-07-17T07:46:00Z",
    },
    {
      role: "assistant",
      kind: "artifact",
      content: "The digest summary, trimmed to the two signals.",
      artifact: {
        artifactId: "conv_6_ar1",
        kind: "summary",
        name: "market-signals-week-29.md",
        size: "3.1 KB",
        preview: "1. Competitor C's usage tiers are landing badly with mid-market — three public complaints this week.\n2. A procurement framework update opens the public-sector door in Q4.",
      },
      createdAt: "2026-07-17T07:47:00Z",
    },
  ]),

  conv_7: makeMessages("conv_7", [
    {
      role: "user",
      content: "Byte, why does the backend README say pytest when nothing uses it?",
      createdAt: "2026-07-11T16:00:00Z",
    },
    {
      role: "assistant",
      kind: "memory_reference",
      content: "Because the README predates the decision — the suite runs with unittest, and that's recorded here.",
      memoryRef: { memoryId: "mem_2", title: "Tests run with unittest, not pytest" },
      createdAt: "2026-07-11T16:01:00Z",
    },
    {
      role: "user",
      content: "Right. Filed a docs fix; archiving this.",
      createdAt: "2026-07-11T16:10:00Z",
    },
  ]),

  conv_8: makeMessages("conv_8", [
    {
      role: "user",
      content: "Nova, the June revenue rollup — where is it, and why did the draft stall?",
      createdAt: "2026-07-12T13:00:00Z",
    },
    {
      role: "assistant",
      kind: "workflow_reference",
      content: "The rollup runs monthly through this workflow; June's run stopped at the export step.",
      workflowRef: { workflowId: "wfl_6", workflowName: "Monthly revenue rollup" },
      createdAt: "2026-07-12T13:01:00Z",
    },
    {
      role: "assistant",
      kind: "memory_reference",
      content: "The export follows the Q3 billing schema — the stall is a renamed column, not missing data.",
      memoryRef: { memoryId: "mem_5", title: "Q3 billing export schema" },
      createdAt: "2026-07-12T13:02:00Z",
    },
    {
      role: "assistant",
      kind: "approval_request",
      content: "I can remap the renamed column and re-run, but that touches the finance export config.",
      approval: {
        approvalId: "conv_8_ap1",
        title: "Remap billing export column and re-run",
        description: "Rename-only change: `acct_ref` → `account_reference`. No values change.",
        status: "REJECTED",
        comment: "Hold — finance wants to make this change on their side first.",
      },
      createdAt: "2026-07-12T13:15:00Z",
    },
    {
      role: "system",
      kind: "notification",
      content: "The June rollup is paused until finance updates the export.",
      notification: { tone: "warning", headline: "June rollup paused pending the finance-side fix." },
      createdAt: "2026-07-12T13:16:00Z",
    },
  ]),
};

export { MESSAGES_BY_CONVERSATION };

// =====================================================================
// Conversations
// =====================================================================

export const CONVERSATIONS: ConversationDetail[] = [
  {
    id: "conv_1",
    employee: EMPLOYEES.emp_1,
    title: "Q3 competitor pricing brief",
    status: "active",
    createdAt: "2026-07-14T09:00:00Z",
    updatedAt: "2026-07-16T08:42:00Z",
    lastMessagePreview: "Tightened. The tiering section now leads with the price-per-unit curve…",
    unreadCount: 0,
    pinned: true,
    shared: false,
    tags: ["research", "pricing"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_1", name: "Atlas", role: "assistant", detail: "Research analyst" },
    ],
    messageCount: 11,
    referencedWorkflows: [{ workflowId: "wfl_1", workflowName: "Weekly competitor brief" }],
    referencedTasks: [{ taskId: "tsk_1", businessId: "TASK-1001", taskName: "Weekly competitor brief" }],
    referencedMemories: [{ memoryId: "mem_1", title: "Competitor A moved to per-seat pricing" }],
    pinnedItems: [
      {
        id: "conv_1_p1",
        label: "Q3 competitor pricing brief (draft)",
        kind: "artifact",
        href: null,
      },
      {
        id: "conv_1_p2",
        label: "Weekly competitor brief",
        kind: "workflow",
        href: "/workspace/workflows/wfl_1",
      },
    ],
  },
  {
    id: "conv_2",
    employee: EMPLOYEES.emp_2,
    title: "Dependency upgrade sweep",
    status: "active",
    createdAt: "2026-07-15T11:20:00Z",
    updatedAt: "2026-07-16T09:06:00Z",
    lastMessagePreview: "Check step fixed and re-queued. I'll report back when the majors decision is due.",
    unreadCount: 2,
    pinned: false,
    shared: false,
    tags: ["engineering"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_2", name: "Byte", role: "assistant", detail: "Engineering assistant" },
    ],
    messageCount: 7,
    referencedWorkflows: [{ workflowId: "wfl_4", workflowName: "Dependency upgrade sweep" }],
    referencedTasks: [{ taskId: "tsk_4", businessId: "TASK-1004", taskName: "Dependency upgrade sweep" }],
    referencedMemories: [{ memoryId: "mem_2", title: "Tests run with unittest, not pytest" }],
    pinnedItems: [
      { id: "conv_2_p1", label: "lockfile-diff.patch", kind: "artifact", href: null },
    ],
  },
  {
    id: "conv_3",
    employee: EMPLOYEES.emp_3,
    title: "Acme renewal follow-up",
    status: "active",
    createdAt: "2026-07-13T14:00:00Z",
    updatedAt: "2026-07-13T15:31:00Z",
    lastMessagePreview: "Conversation shared with the account team.",
    unreadCount: 0,
    pinned: false,
    shared: true,
    tags: ["accounts"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_3", name: "Vera", role: "assistant", detail: "Customer success" },
    ],
    messageCount: 6,
    referencedWorkflows: [],
    referencedTasks: [],
    referencedMemories: [{ memoryId: "mem_3", title: "Acme is on the legacy annual plan" }],
    pinnedItems: [
      { id: "conv_3_p1", label: "acme-renewal-one-pager.docx", kind: "document", href: null },
    ],
  },
  {
    id: "conv_4",
    employee: EMPLOYEES.emp_4,
    title: "July launch notes",
    status: "active",
    createdAt: "2026-07-16T10:00:00Z",
    updatedAt: "2026-07-16T12:05:00Z",
    lastMessagePreview: "Nice. I'll add the customer line tonight.",
    unreadCount: 0,
    pinned: true,
    shared: false,
    tags: ["marketing"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_4", name: "Nova", role: "assistant", detail: "Marketing writer" },
    ],
    messageCount: 5,
    referencedWorkflows: [{ workflowId: "wfl_5", workflowName: "Release notes draft" }],
    referencedTasks: [],
    referencedMemories: [{ memoryId: "mem_4", title: "House voice: sentence case, never title case" }],
    pinnedItems: [
      { id: "conv_4_p1", label: "july-launch-notes.md", kind: "document", href: null },
      { id: "conv_4_p2", label: "Release notes draft", kind: "workflow", href: "/workspace/workflows/wfl_5" },
    ],
  },
  {
    id: "conv_5",
    employee: EMPLOYEES.emp_6,
    title: "Beta inbox triage rules",
    status: "archived",
    createdAt: "2026-07-10T09:30:00Z",
    updatedAt: "2026-07-10T10:00:00Z",
    lastMessagePreview: "That covers it. Archiving this until the beta actually opens.",
    unreadCount: 0,
    pinned: false,
    shared: false,
    tags: ["operations"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_6", name: "Echo", role: "assistant", detail: "Operations coordinator" },
    ],
    messageCount: 4,
    referencedWorkflows: [{ workflowId: "wfl_9", workflowName: "Inbox triage" }],
    referencedTasks: [],
    referencedMemories: [],
    pinnedItems: [],
  },
  {
    id: "conv_6",
    employee: EMPLOYEES.emp_1,
    title: "Week 29 market signals",
    status: "active",
    createdAt: "2026-07-17T07:45:00Z",
    updatedAt: "2026-07-17T07:47:00Z",
    lastMessagePreview: "The digest summary, trimmed to the two signals.",
    unreadCount: 1,
    pinned: false,
    shared: true,
    tags: ["research"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_1", name: "Atlas", role: "assistant", detail: "Research analyst" },
    ],
    messageCount: 3,
    referencedWorkflows: [{ workflowId: "wfl_2", workflowName: "Market signal digest" }],
    referencedTasks: [],
    referencedMemories: [],
    pinnedItems: [],
  },
  {
    id: "conv_7",
    employee: EMPLOYEES.emp_2,
    title: "Test runner docs mismatch",
    status: "archived",
    createdAt: "2026-07-11T16:00:00Z",
    updatedAt: "2026-07-11T16:10:00Z",
    lastMessagePreview: "Right. Filed a docs fix; archiving this.",
    unreadCount: 0,
    pinned: false,
    shared: false,
    tags: ["engineering"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_2", name: "Byte", role: "assistant", detail: "Engineering assistant" },
    ],
    messageCount: 3,
    referencedWorkflows: [],
    referencedTasks: [],
    referencedMemories: [{ memoryId: "mem_2", title: "Tests run with unittest, not pytest" }],
    pinnedItems: [],
  },
  {
    id: "conv_8",
    employee: EMPLOYEES.emp_4,
    title: "June revenue rollup stall",
    status: "active",
    createdAt: "2026-07-12T13:00:00Z",
    updatedAt: "2026-07-12T13:16:00Z",
    lastMessagePreview: "The June rollup is paused until finance updates the export.",
    unreadCount: 0,
    pinned: false,
    shared: false,
    tags: ["finance"],
    participants: [
      { id: OWNER.id, name: OWNER.name, role: "user", detail: OWNER.detail },
      { id: "emp_4", name: "Nova", role: "assistant", detail: "Marketing writer" },
    ],
    messageCount: 5,
    referencedWorkflows: [{ workflowId: "wfl_6", workflowName: "Monthly revenue rollup" }],
    referencedTasks: [{ taskId: "tsk_6", businessId: "TASK-1006", taskName: "Monthly revenue rollup" }],
    referencedMemories: [{ memoryId: "mem_5", title: "Q3 billing export schema" }],
    pinnedItems: [],
  },
];

// =====================================================================
// Scripted replies
// =====================================================================

/**
 * What an employee says back when the user sends a message. Deterministic and
 * scripted: the adapter cycles through a conversation's list by how many user
 * messages the thread holds, so the same send always meets the same reply.
 * Nothing generates — these are fixtures pretending to be Sprint 5's
 * `/generate` endpoint, and they say so on their face.
 */
export const SCRIPTED_REPLIES: Record<string, string[]> = {
  conv_1: [
    "Noted — I've folded that into the brief. The updated draft will be in this thread shortly.",
    "Good call. I'll cross-check that against the memory record before it goes in.",
    "Done. Anything else before I hand this to the planning review?",
  ],
  conv_2: [
    "Logged. The sweep will pick that up on its next pass — I'll flag anything that fails the check step.",
    "Understood. Holding the majors and noting your reasoning on the task.",
  ],
  conv_3: [
    "Will do — I'll brief the account team and keep the renewal timeline in this thread.",
    "Noted. I'll have the follow-up summary ready before Thursday's call.",
  ],
  conv_4: [
    "Got it — I'll weave that in and keep the voice rules intact.",
    "Drafting now. I'll post the revision as an artifact here.",
  ],
  conv_5: ["This conversation is archived — restore it from settings and I'll pick the triage rules back up."],
  conv_6: [
    "I'll add that angle to next week's digest scope.",
    "Noted — flagging that signal for a deeper look.",
  ],
  conv_7: ["This conversation is archived — restore it and I'll take another look at the docs."],
  conv_8: [
    "Understood. I'll watch for the finance-side fix and re-run the rollup the moment it lands.",
    "Noted — the rollup stays paused until you say otherwise.",
  ],
};

/** The reply when a conversation has no script left — never silence. */
export const FALLBACK_REPLY =
  "Noted. I've added that to this conversation's context and will pick it up in the next pass.";

// =====================================================================
// Suggestions
// =====================================================================

/** Chips every conversation offers. */
export const GLOBAL_SUGGESTIONS: Suggestion[] = [
  { id: "sug_g1", kind: "prompt", label: "Summarise this conversation", insertText: "Summarise this conversation in five bullets." },
  { id: "sug_g2", kind: "prompt", label: "What's blocked right now?", insertText: "What's blocked right now, and what do you need from me?" },
  { id: "sug_g3", kind: "action", label: "Draft next steps", insertText: "Draft the next steps as a checklist I can turn into a task." },
  { id: "sug_g4", kind: "task", label: "Weekly competitor brief", insertText: "Check on task TASK-1001 (Weekly competitor brief)." },
  { id: "sug_g5", kind: "workflow", label: "Market signal digest", insertText: "Run the Market signal digest workflow and post the summary here." },
  { id: "sug_g6", kind: "memory", label: "House voice rules", insertText: "Apply the house voice rules from memory to the current draft." },
  { id: "sug_g7", kind: "employee", label: "Loop in Vera", insertText: "Loop in @Vera for the customer-facing side of this." },
];

/** Extra chips per conversation, ahead of the global ones. */
export const CONVERSATION_SUGGESTIONS: Record<string, Suggestion[]> = {
  conv_1: [
    { id: "sug_c1a", kind: "action", label: "Decide the pending approval", insertText: "Let's settle the restricted data question — walk me through the trade-off once more." },
    { id: "sug_c1b", kind: "workflow", label: "Re-run competitor brief", insertText: "Re-run the Weekly competitor brief workflow with this week's data." },
  ],
  conv_2: [
    { id: "sug_c2a", kind: "task", label: "Check sweep status", insertText: "What's the current state of TASK-1004?" },
  ],
  conv_6: [
    { id: "sug_c6a", kind: "prompt", label: "Expand signal two", insertText: "Expand on the procurement framework signal — what would Q4 readiness take?" },
  ],
};
