import type {
  Actor,
  ActivityEvent,
  CollaborationApproval,
  Comment,
  NotificationDetail,
  RelatedEntity,
} from "./types";

/**
 * Deterministic collaboration fixtures. No randomness, no clock reads — every
 * timestamp is pinned so the same screen renders the same bytes on the server
 * and the client. Identities reuse the platform's own cast: employees
 * (`emp_*`), workflows (`wfl_*`), tasks (`tsk_*`), memories (`mem_*`) and
 * conversations (`conv_*`) all match the records the rest of the workspace
 * shows, so a reference in the inspector points somewhere real.
 */

// =====================================================================
// Cast
// =====================================================================

export const OWNER: Actor = { id: "user_1", name: "Himanshu", kind: "user", detail: "Workspace owner" };

type EmployeeKey = "emp_1" | "emp_2" | "emp_3" | "emp_4" | "emp_6";

export const EMPLOYEE_ACTORS: Record<EmployeeKey, Actor> = {
  emp_1: { id: "emp_1", name: "Atlas", kind: "employee", detail: "Research analyst" },
  emp_2: { id: "emp_2", name: "Byte", kind: "employee", detail: "Engineering assistant" },
  emp_3: { id: "emp_3", name: "Vera", kind: "employee", detail: "Customer success" },
  emp_4: { id: "emp_4", name: "Nova", kind: "employee", detail: "Marketing writer" },
  emp_6: { id: "emp_6", name: "Echo", kind: "employee", detail: "Operations coordinator" },
};

export const SYSTEM_ACTOR: Actor = { id: "system", name: "NeuraEvo", kind: "system", detail: "Platform" };

/** Teammates for the team feed and watcher lists. Identity only — mock. */
export const TEAMMATES: Record<"tm_1" | "tm_2" | "tm_3", Actor> = {
  tm_1: { id: "tm_1", name: "Priya Nair", kind: "user", detail: "Product lead" },
  tm_2: { id: "tm_2", name: "Marcus Cole", kind: "user", detail: "Finance" },
  tm_3: { id: "tm_3", name: "Dana Ruiz", kind: "user", detail: "Account manager" },
};

// =====================================================================
// Reference builders — keep the fixtures compact and consistent
// =====================================================================

const emp = (id: keyof typeof EMPLOYEE_ACTORS, roleTitle: string): RelatedEntity => ({
  kind: "employee",
  employee: { employeeId: id, employeeName: EMPLOYEE_ACTORS[id].name, roleTitle },
});
const wf = (workflowId: string, workflowName: string): RelatedEntity => ({
  kind: "workflow",
  workflow: { workflowId, workflowName },
});
const tk = (taskId: string, businessId: string, taskName: string): RelatedEntity => ({
  kind: "task",
  task: { taskId, businessId, taskName },
});
const mem = (memoryId: string, title: string): RelatedEntity => ({
  kind: "memory",
  memory: { memoryId, title },
});
const conv = (conversationId: string, title: string, employeeName: string): RelatedEntity => ({
  kind: "conversation",
  conversation: { conversationId, title, employeeName },
});

// =====================================================================
// Notifications
// =====================================================================

export const NOTIFICATIONS: NotificationDetail[] = [
  {
    id: "ntf_1",
    type: "approval",
    title: "Approval needed: restricted win/loss data",
    description: "Atlas is waiting on your sign-off before adding restricted deals data to the Q3 brief.",
    source: EMPLOYEE_ACTORS.emp_1,
    createdAt: "2026-07-17T09:15:00Z",
    priority: "HIGH",
    read: false,
    archived: false,
    pinned: true,
    bookmarked: true,
    following: true,
    muted: false,
    primaryEntity: conv("conv_1", "Q3 competitor pricing brief", "Atlas"),
    isMention: false,
    relatedEntities: [
      conv("conv_1", "Q3 competitor pricing brief", "Atlas"),
      wf("wfl_1", "Weekly competitor brief"),
      emp("emp_1", "Research analyst"),
    ],
    history: [
      { id: "ntf_1_h1", kind: "created", summary: "Approval requested", actor: EMPLOYEE_ACTORS.emp_1, createdAt: "2026-07-17T09:15:00Z" },
    ],
    comments: [
      { id: "ntf_1_c1", actor: TEAMMATES.tm_1, body: "Fine to include for the planning review, but flag it as restricted in the footnote.", createdAt: "2026-07-17T09:40:00Z" },
    ],
    watchers: [OWNER, TEAMMATES.tm_1],
  },
  {
    id: "ntf_2",
    type: "task",
    title: "Dependency upgrade sweep is waiting on approval",
    description: "Byte held back two major upgrades pending your review.",
    source: EMPLOYEE_ACTORS.emp_2,
    createdAt: "2026-07-16T09:05:00Z",
    priority: "MEDIUM",
    read: false,
    archived: false,
    pinned: false,
    bookmarked: false,
    following: true,
    muted: false,
    primaryEntity: tk("tsk_4", "TASK-1004", "Dependency upgrade sweep"),
    isMention: false,
    relatedEntities: [tk("tsk_4", "TASK-1004", "Dependency upgrade sweep"), emp("emp_2", "Engineering assistant")],
    history: [
      { id: "ntf_2_h1", kind: "updated", summary: "Task moved to waiting approval", actor: EMPLOYEE_ACTORS.emp_2, createdAt: "2026-07-16T09:05:00Z" },
    ],
    comments: [],
    watchers: [OWNER],
  },
  {
    id: "ntf_3",
    type: "conversation",
    title: "Priya mentioned you in “Q3 competitor pricing brief”",
    description: "“@Himanshu can you confirm the tiering numbers before this goes to the review?”",
    source: TEAMMATES.tm_1,
    createdAt: "2026-07-16T14:20:00Z",
    priority: "MEDIUM",
    read: false,
    archived: false,
    pinned: false,
    bookmarked: true,
    following: false,
    muted: false,
    primaryEntity: conv("conv_1", "Q3 competitor pricing brief", "Atlas"),
    isMention: true,
    relatedEntities: [conv("conv_1", "Q3 competitor pricing brief", "Atlas")],
    history: [
      { id: "ntf_3_h1", kind: "mentioned", summary: "You were mentioned", actor: TEAMMATES.tm_1, createdAt: "2026-07-16T14:20:00Z" },
    ],
    comments: [],
    watchers: [OWNER, TEAMMATES.tm_1],
  },
  {
    id: "ntf_4",
    type: "workflow",
    title: "Market signal digest finished",
    description: "This week's digest completed and posted two signals to the Week 29 conversation.",
    source: EMPLOYEE_ACTORS.emp_1,
    createdAt: "2026-07-17T07:47:00Z",
    priority: "LOW",
    read: true,
    archived: false,
    pinned: false,
    bookmarked: false,
    following: true,
    muted: false,
    primaryEntity: wf("wfl_2", "Market signal digest"),
    isMention: false,
    relatedEntities: [wf("wfl_2", "Market signal digest"), conv("conv_6", "Week 29 market signals", "Atlas")],
    history: [
      { id: "ntf_4_h1", kind: "completed", summary: "Workflow completed", actor: EMPLOYEE_ACTORS.emp_1, createdAt: "2026-07-17T07:47:00Z" },
    ],
    comments: [],
    watchers: [OWNER],
  },
  {
    id: "ntf_5",
    type: "memory",
    title: "New memory learned: Q3 billing export schema",
    description: "Nova recorded the renamed billing column while investigating the June rollup stall.",
    source: EMPLOYEE_ACTORS.emp_4,
    createdAt: "2026-07-12T13:02:00Z",
    priority: "LOW",
    read: true,
    archived: false,
    pinned: false,
    bookmarked: false,
    following: false,
    muted: false,
    primaryEntity: mem("mem_5", "Q3 billing export schema"),
    isMention: false,
    relatedEntities: [mem("mem_5", "Q3 billing export schema"), conv("conv_8", "June revenue rollup stall", "Nova")],
    history: [
      { id: "ntf_5_h1", kind: "created", summary: "Memory recorded", actor: EMPLOYEE_ACTORS.emp_4, createdAt: "2026-07-12T13:02:00Z" },
    ],
    comments: [
      { id: "ntf_5_c1", actor: TEAMMATES.tm_2, body: "Finance will make the rename on our side first — hold the remap.", createdAt: "2026-07-12T13:20:00Z" },
    ],
    watchers: [OWNER, TEAMMATES.tm_2],
  },
  {
    id: "ntf_6",
    type: "approval",
    title: "Approval rejected: billing export remap",
    description: "You held Nova's request to remap the finance export column until finance updates it.",
    source: EMPLOYEE_ACTORS.emp_4,
    createdAt: "2026-07-12T13:16:00Z",
    priority: "MEDIUM",
    read: true,
    archived: false,
    pinned: false,
    bookmarked: false,
    following: false,
    muted: false,
    primaryEntity: tk("tsk_6", "TASK-1006", "Monthly revenue rollup"),
    isMention: false,
    relatedEntities: [tk("tsk_6", "TASK-1006", "Monthly revenue rollup"), wf("wfl_6", "Monthly revenue rollup")],
    history: [
      { id: "ntf_6_h1", kind: "rejected", summary: "Approval rejected", actor: OWNER, createdAt: "2026-07-12T13:16:00Z" },
    ],
    comments: [],
    watchers: [OWNER],
  },
  {
    id: "ntf_7",
    type: "employee",
    title: "Vera closed the Acme renewal thread",
    description: "The renewal one-pager was shared with the account team.",
    source: EMPLOYEE_ACTORS.emp_3,
    createdAt: "2026-07-13T15:31:00Z",
    priority: "LOW",
    read: true,
    archived: false,
    pinned: false,
    bookmarked: false,
    following: false,
    muted: true,
    primaryEntity: emp("emp_3", "Customer success"),
    isMention: false,
    relatedEntities: [emp("emp_3", "Customer success"), conv("conv_3", "Acme renewal follow-up", "Vera")],
    history: [
      { id: "ntf_7_h1", kind: "completed", summary: "Conversation shared with the account team", actor: EMPLOYEE_ACTORS.emp_3, createdAt: "2026-07-13T15:31:00Z" },
    ],
    comments: [],
    watchers: [OWNER, TEAMMATES.tm_3],
  },
  {
    id: "ntf_8",
    type: "task",
    title: "Weekly competitor brief assigned to Atlas",
    description: "A task was created from the Q3 pricing conversation and assigned to Atlas.",
    source: SYSTEM_ACTOR,
    createdAt: "2026-07-14T09:06:00Z",
    priority: "LOW",
    read: true,
    archived: false,
    pinned: false,
    bookmarked: false,
    following: false,
    muted: false,
    primaryEntity: tk("tsk_1", "TASK-1001", "Weekly competitor brief"),
    isMention: false,
    relatedEntities: [tk("tsk_1", "TASK-1001", "Weekly competitor brief"), emp("emp_1", "Research analyst")],
    history: [
      { id: "ntf_8_h1", kind: "assigned", summary: "Task assigned to Atlas", actor: SYSTEM_ACTOR, createdAt: "2026-07-14T09:06:00Z" },
    ],
    comments: [],
    watchers: [OWNER],
  },
  {
    id: "ntf_9",
    type: "system",
    title: "Weekly usage summary is ready",
    description: "Your workspace ran 12 tasks and 4 workflows this week, with 2 approvals pending.",
    source: SYSTEM_ACTOR,
    createdAt: "2026-07-13T06:00:00Z",
    priority: "LOW",
    read: true,
    archived: true,
    pinned: false,
    bookmarked: false,
    following: false,
    muted: false,
    primaryEntity: null,
    isMention: false,
    relatedEntities: [],
    history: [
      { id: "ntf_9_h1", kind: "created", summary: "Summary generated", actor: SYSTEM_ACTOR, createdAt: "2026-07-13T06:00:00Z" },
    ],
    comments: [],
    watchers: [OWNER],
  },
  {
    id: "ntf_10",
    type: "conversation",
    title: "Dana bookmarked “Acme renewal follow-up”",
    description: "Dana Ruiz is now following the Acme renewal thread for the account team.",
    source: TEAMMATES.tm_3,
    createdAt: "2026-07-13T16:00:00Z",
    priority: "LOW",
    read: true,
    archived: false,
    pinned: false,
    bookmarked: false,
    following: false,
    muted: false,
    primaryEntity: conv("conv_3", "Acme renewal follow-up", "Vera"),
    isMention: false,
    relatedEntities: [conv("conv_3", "Acme renewal follow-up", "Vera")],
    history: [
      { id: "ntf_10_h1", kind: "updated", summary: "Dana started following", actor: TEAMMATES.tm_3, createdAt: "2026-07-13T16:00:00Z" },
    ],
    comments: [],
    watchers: [OWNER, TEAMMATES.tm_3],
  },
];

// =====================================================================
// Activity feed
// =====================================================================

const ev = (
  id: string,
  kind: ActivityEvent["kind"],
  actor: Actor,
  summary: string,
  entity: RelatedEntity | null,
  createdAt: string,
  isOwn: boolean
): ActivityEvent => ({ id, kind, actor, summary, entity, createdAt, isOwn });

export const ACTIVITY: ActivityEvent[] = [
  ev("act_1", "mentioned", TEAMMATES.tm_1, "Priya mentioned you in Q3 competitor pricing brief", conv("conv_1", "Q3 competitor pricing brief", "Atlas"), "2026-07-16T14:20:00Z", true),
  ev("act_2", "approved", OWNER, "You approved the restricted win/loss data", conv("conv_1", "Q3 competitor pricing brief", "Atlas"), "2026-07-17T10:05:00Z", true),
  ev("act_3", "completed", EMPLOYEE_ACTORS.emp_1, "Atlas completed the market signal digest", wf("wfl_2", "Market signal digest"), "2026-07-17T07:47:00Z", false),
  ev("act_4", "commented", TEAMMATES.tm_2, "Marcus commented on the billing export memory", mem("mem_5", "Q3 billing export schema"), "2026-07-12T13:20:00Z", false),
  ev("act_5", "created", SYSTEM_ACTOR, "Weekly competitor brief was created from a conversation", tk("tsk_1", "TASK-1001", "Weekly competitor brief"), "2026-07-14T09:06:00Z", false),
  ev("act_6", "assigned", SYSTEM_ACTOR, "Weekly competitor brief was assigned to Atlas", emp("emp_1", "Research analyst"), "2026-07-14T09:06:30Z", false),
  ev("act_7", "rejected", OWNER, "You rejected the billing export remap", tk("tsk_6", "TASK-1006", "Monthly revenue rollup"), "2026-07-12T13:16:00Z", true),
  ev("act_8", "updated", EMPLOYEE_ACTORS.emp_2, "Byte re-queued the dependency upgrade sweep", tk("tsk_4", "TASK-1004", "Dependency upgrade sweep"), "2026-07-16T09:06:00Z", false),
  ev("act_9", "archived", EMPLOYEE_ACTORS.emp_6, "Echo archived the beta inbox triage thread", conv("conv_5", "Beta inbox triage rules", "Echo"), "2026-07-10T10:00:00Z", false),
  ev("act_10", "created", EMPLOYEE_ACTORS.emp_4, "Nova drafted the July launch notes", conv("conv_4", "July launch notes", "Nova"), "2026-07-16T10:20:00Z", false),
  ev("act_11", "commented", TEAMMATES.tm_1, "Priya commented on the Q3 pricing brief approval", conv("conv_1", "Q3 competitor pricing brief", "Atlas"), "2026-07-17T09:40:00Z", false),
  ev("act_12", "completed", EMPLOYEE_ACTORS.emp_3, "Vera closed the Acme renewal thread", conv("conv_3", "Acme renewal follow-up", "Vera"), "2026-07-13T15:31:00Z", false),
];

// =====================================================================
// Approvals inbox
// =====================================================================

export const APPROVALS: CollaborationApproval[] = [
  {
    id: "cap_1",
    title: "Include restricted win/loss data",
    description: "The Q3 brief reads better with the win/loss trend, but that sheet is marked restricted.",
    status: "PENDING",
    priority: "HIGH",
    requestedBy: EMPLOYEE_ACTORS.emp_1,
    createdAt: "2026-07-17T09:15:00Z",
    entity: conv("conv_1", "Q3 competitor pricing brief", "Atlas"),
    comment: null,
  },
  {
    id: "cap_2",
    title: "Promote two major dependency upgrades",
    description: "Byte held back query-runtime 5→6 and motion-core 11→12 pending your review.",
    status: "PENDING",
    priority: "MEDIUM",
    requestedBy: EMPLOYEE_ACTORS.emp_2,
    createdAt: "2026-07-16T09:05:00Z",
    entity: tk("tsk_4", "TASK-1004", "Dependency upgrade sweep"),
    comment: null,
  },
  {
    id: "cap_3",
    title: "Approve 12% renewal discount for Acme",
    description: "Standard ceiling is 10%; the extra 2% matches Competitor A's March quote.",
    status: "APPROVED",
    priority: "MEDIUM",
    requestedBy: EMPLOYEE_ACTORS.emp_3,
    createdAt: "2026-07-13T14:10:00Z",
    entity: conv("conv_3", "Acme renewal follow-up", "Vera"),
    comment: "Approved — worth it for a two-year term.",
  },
  {
    id: "cap_4",
    title: "Remap billing export column and re-run",
    description: "Rename-only change: acct_ref → account_reference. No values change.",
    status: "REJECTED",
    priority: "MEDIUM",
    requestedBy: EMPLOYEE_ACTORS.emp_4,
    createdAt: "2026-07-12T13:15:00Z",
    entity: tk("tsk_6", "TASK-1006", "Monthly revenue rollup"),
    comment: "Hold — finance wants to make this change on their side first.",
  },
];

/** A stable extra comment for the composer to append onto in the mock. */
export const OWNER_COMMENT_AUTHOR = OWNER;
export type { Comment };
