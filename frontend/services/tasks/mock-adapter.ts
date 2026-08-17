import type { WorkflowRunPage } from "@/services/workflows";
import { APPROVALS, ARTIFACTS, QUEUE_ORDER, TASKS, TIMELINES } from "./fixtures";
import {
  COMMAND_RESULT,
  TASK_STATE_LABEL,
  TaskError,
  isCommandAllowed,
  type Approval,
  type ApprovalDecision,
  type Artifact,
  type QueueEntry,
  type QueueSnapshot,
  type TaskCommand,
  type TaskDetail,
  type TaskDraft,
  type TaskSummary,
  type TasksAdapter,
  type TimelineEvent,
} from "./types";

/**
 * Deterministic in-browser mock of a task backend. No network, no clock, no
 * randomness. Writes go to localStorage to simulate server persistence so a
 * created task survives a reload — the same approach `MockEmployeesAdapter`
 * (17.6), `MockWorkflowsAdapter` (17.5) and `MockAuthAdapter` (17.2) use.
 *
 * This mock stores descriptions of runs. It never executes one: no step is
 * advanced, no progress ticks, no state moves on its own. A task's state changes
 * only when the user asks for it through `command`, and even then this records
 * the *request* — the real platform is what would carry it out.
 */

const STORE_KEY = "neuraevo.mock.tasks";
const APPROVAL_KEY = "neuraevo.mock.tasks.approvals";
const TIMELINE_KEY = "neuraevo.mock.tasks.timelines";
const LATENCY_MS = 350;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

/** Structured clone via JSON — fixtures and stored rows are plain data. */
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

type TimelineLog = Record<string, TimelineEvent[]>;

function read<T>(key: string, seed: () => T): T {
  if (typeof window === "undefined") return seed();
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return seed();
    const parsed = JSON.parse(raw) as T;
    return parsed ?? seed();
  } catch {
    return seed();
  }
}

function write(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* quota or private mode — the change simply doesn't persist */
  }
}

const readTasks = (): TaskDetail[] => {
  const rows = read<TaskDetail[]>(STORE_KEY, () => copy(TASKS) as TaskDetail[]);
  return Array.isArray(rows) ? rows : (copy(TASKS) as TaskDetail[]);
};
const writeTasks = (rows: TaskDetail[]) => write(STORE_KEY, rows);

const readApprovals = (): Approval[] => {
  const rows = read<Approval[]>(APPROVAL_KEY, () => copy(APPROVALS) as Approval[]);
  return Array.isArray(rows) ? rows : (copy(APPROVALS) as Approval[]);
};
const writeApprovals = (rows: Approval[]) => write(APPROVAL_KEY, rows);

const readTimelines = (): TimelineLog => read<TimelineLog>(TIMELINE_KEY, () => copy(TIMELINES) as TimelineLog);
const writeTimelines = (log: TimelineLog) => write(TIMELINE_KEY, log);

/**
 * Appends one event to a task's timeline. History is append-only: an event
 * records that something happened, so it is never rewritten or removed.
 */
function logEvent(taskId: string, kind: TimelineEvent["kind"], summary: string) {
  const log = readTimelines();
  const events = log[taskId] ?? [];
  const sequence = events.reduce((max, e) => Math.max(max, e.sequence), 0) + 1;
  log[taskId] = [{ id: `tl_${taskId}_${sequence}`, kind, summary, nodeId: null, sequence }, ...events];
  writeTimelines(log);
}

const toSummary = (task: TaskDetail): TaskSummary => ({
  id: task.id,
  businessId: task.businessId,
  name: task.name,
  description: task.description,
  state: task.state,
  priority: task.priority,
  executionMode: task.executionMode,
  workflow: task.workflow,
  assignee: task.assignee,
  progress: task.progress,
  queuePosition: task.queuePosition,
  sequence: task.sequence,
});

/** Deterministic id from the existing rows — no randomness, no timestamps. */
function nextId(rows: TaskDetail[], prefix: string): string {
  let n = rows.length + 1;
  while (rows.some((r) => r.id === `${prefix}_${n}`)) n++;
  return `${prefix}_${n}`;
}

/** Business ids continue the fixture series rather than restarting. */
function nextBusinessId(rows: TaskDetail[]): string {
  const highest = rows.reduce((max, r) => {
    const n = Number.parseInt(r.businessId.replace(/^\D+/, ""), 10);
    return Number.isNaN(n) ? max : Math.max(max, n);
  }, 1032);
  return `TSK-${highest + 1}`;
}

const nextSequence = (rows: TaskDetail[]): number =>
  rows.reduce((max, r) => Math.max(max, r.sequence), 0) + 1;

/** Keeps a task's own monitor telling the same story as its state. */
function withState(task: TaskDetail, command: TaskCommand): TaskDetail {
  const state = COMMAND_RESULT[command];
  const isRestart = command === "retry" || command === "queue";

  return {
    ...task,
    state,
    // A retry starts over: the previous run's progress and findings aren't this
    // run's. Everything else keeps what it had, because pausing doesn't undo work.
    progress: isRestart ? 0 : task.progress,
    queuePosition: state === "QUEUED" ? queuePositionFor(task) : null,
    monitor: {
      ...task.monitor,
      state,
      progress: isRestart ? 0 : task.monitor.progress,
      completedSteps: isRestart ? 0 : task.monitor.completedSteps,
      currentNodeId: isRestart ? null : task.monitor.currentNodeId,
      executionPath: isRestart ? [] : task.monitor.executionPath,
      errors: isRestart ? [] : task.monitor.errors,
    },
    result: isRestart ? null : task.result,
  };
}

/** Where a task joins the line: at the back, as the platform would put it. */
function queuePositionFor(task: TaskDetail): number {
  const queued = readTasks().filter((t) => t.state === "QUEUED" && t.id !== task.id);
  return queued.length + 1;
}

export class MockTasksAdapter implements TasksAdapter {
  async list(): Promise<TaskSummary[]> {
    await delay();
    return readTasks()
      .slice()
      .sort((a, b) => b.sequence - a.sequence)
      .map(toSummary);
  }

  async detail(id: string): Promise<TaskDetail> {
    await delay();
    const found = readTasks().find((t) => t.id === id);
    if (!found) throw new TaskError("not_found", "That task doesn't exist.");
    return copy(found);
  }

  async create(draft: TaskDraft): Promise<TaskDetail> {
    await delay();
    if (!draft.name.trim()) throw new TaskError("invalid_draft", "A task needs a name.");

    const rows = readTasks();
    const id = nextId(rows, "tsk");

    const created: TaskDetail = {
      id,
      businessId: nextBusinessId(rows),
      name: draft.name.trim(),
      description: draft.description.trim(),
      // A task is described, not started. It opens PENDING and stays there until
      // someone queues it — this layer never starts anything.
      state: "PENDING",
      priority: draft.priority,
      executionMode: draft.executionMode,
      workflow: null,
      assignee: null,
      progress: 0,
      queuePosition: null,
      sequence: nextSequence(rows),
      // No workflow and no employee yet means there is no run to draw.
      graph: { nodes: [], edges: [] },
      monitor: {
        state: "PENDING",
        health: "UNKNOWN",
        progress: 0,
        completedSteps: 0,
        totalSteps: 0,
        currentNodeId: null,
        executionPath: [],
        warnings: [],
        errors: [],
      },
      result: null,
    };

    rows.push(created);
    writeTasks(rows);
    logEvent(id, "TASK_CREATED", `${created.businessId} created`);

    // Assignments are separate operations so a create and an edit take the same
    // path through the adapter.
    let result = created;
    if (draft.workflowId) result = await this.assignWorkflow(id, draft.workflowId);
    if (draft.employeeId) result = await this.assignEmployee(id, draft.employeeId);
    return result;
  }

  async duplicate(id: string): Promise<TaskDetail> {
    await delay();
    const rows = readTasks();
    const source = rows.find((t) => t.id === id);
    if (!source) throw new TaskError("not_found", "That task doesn't exist.");

    const clone: TaskDetail = {
      ...copy(source),
      id: nextId(rows, "tsk"),
      businessId: nextBusinessId(rows),
      name: `${source.name} (copy)`,
      // A copy inherits the plan, never the run: it has done nothing.
      state: "PENDING",
      progress: 0,
      queuePosition: null,
      sequence: nextSequence(rows),
      graph: {
        nodes: source.graph.nodes.map((n) => ({ ...n, status: "PENDING" })),
        edges: copy(source.graph.edges),
      },
      monitor: {
        state: "PENDING",
        health: "UNKNOWN",
        progress: 0,
        completedSteps: 0,
        totalSteps: source.monitor.totalSteps,
        currentNodeId: null,
        executionPath: [],
        warnings: [],
        errors: [],
      },
      result: null,
    };

    rows.push(clone);
    writeTasks(rows);
    logEvent(clone.id, "TASK_CREATED", `${clone.businessId} created from ${source.businessId}`);
    return copy(clone);
  }

  async command(id: string, command: TaskCommand): Promise<TaskDetail> {
    await delay();
    const rows = readTasks();
    const index = rows.findIndex((t) => t.id === id);
    const task = index >= 0 ? rows[index] : undefined;
    if (!task) throw new TaskError("not_found", "That task doesn't exist.");

    // The same table the toolbar reads. A request the state forbids is refused
    // here too, so a stale button can't drive an illegal move.
    if (!isCommandAllowed(task.state, command)) {
      throw new TaskError(
        "not_permitted",
        `A task that's ${TASK_STATE_LABEL[task.state].toLowerCase()} can't be ${command}d.`
      );
    }

    const next = withState(task, command);
    rows[index] = next;
    writeTasks(rows);

    if (command === "queue" || command === "retry") logEvent(id, "QUEUED", `${task.businessId} queued`);
    return copy(next);
  }

  async assignWorkflow(id: string, workflowId: string): Promise<TaskDetail> {
    await delay();
    const rows = readTasks();
    const index = rows.findIndex((t) => t.id === id);
    const task = index >= 0 ? rows[index] : undefined;
    if (!task) throw new TaskError("not_found", "That task doesn't exist.");

    const name = WORKFLOW_NAMES[workflowId] ?? "Unassigned workflow";
    const next: TaskDetail = { ...task, workflow: { workflowId, workflowName: name } };
    rows[index] = next;
    writeTasks(rows);
    return copy(next);
  }

  async assignEmployee(id: string, employeeId: string): Promise<TaskDetail> {
    await delay();
    const rows = readTasks();
    const index = rows.findIndex((t) => t.id === id);
    const task = index >= 0 ? rows[index] : undefined;
    if (!task) throw new TaskError("not_found", "That task doesn't exist.");

    const name = EMPLOYEE_NAMES[employeeId] ?? "Unassigned employee";
    const next: TaskDetail = { ...task, assignee: { employeeId, employeeName: name } };
    rows[index] = next;
    writeTasks(rows);
    return copy(next);
  }

  async timeline(id: string): Promise<TimelineEvent[]> {
    await delay();
    const events = readTimelines()[id] ?? [];
    return copy(events).sort((a, b) => b.sequence - a.sequence);
  }

  async artifacts(id: string): Promise<Artifact[]> {
    await delay();
    const rows = ARTIFACTS[id] ?? [];
    return copy(rows as Artifact[]).sort((a, b) => b.sequence - a.sequence);
  }

  async approvals(id: string): Promise<Approval[]> {
    await delay();
    return readApprovals()
      .filter((a) => a.taskId === id)
      .sort((a, b) => b.sequence - a.sequence);
  }

  async allApprovals(): Promise<Approval[]> {
    await delay();
    return readApprovals().slice().sort((a, b) => b.sequence - a.sequence);
  }

  async decide(decision: ApprovalDecision): Promise<Approval> {
    await delay();
    const rows = readApprovals();
    const index = rows.findIndex((a) => a.id === decision.approvalId);
    const approval = index >= 0 ? rows[index] : undefined;
    if (!approval) throw new TaskError("not_found", "That approval doesn't exist.");
    if (approval.status !== "PENDING") {
      throw new TaskError("not_permitted", "That approval has already been decided.");
    }

    const decided: Approval = {
      ...approval,
      status: decision.status,
      comment: decision.comment.trim() || null,
    };
    rows[index] = decided;
    writeApprovals(rows);

    logEvent(
      approval.taskId,
      "APPROVAL_COMPLETED",
      `${decision.status === "APPROVED" ? "Approved" : "Rejected"}: ${approval.title}`
    );

    // A decision unblocks the task, but it does not run it: the state moves to
    // where the platform would pick it up (or stop), and nothing else advances.
    const tasks = readTasks();
    const taskIndex = tasks.findIndex((t) => t.id === approval.taskId);
    const task = taskIndex >= 0 ? tasks[taskIndex] : undefined;
    if (task && task.state === "WAITING_APPROVAL") {
      const state = decision.status === "APPROVED" ? "QUEUED" : "CANCELLED";
      tasks[taskIndex] = { ...task, state, monitor: { ...task.monitor, state } };
      writeTasks(tasks);
    }

    return copy(decided);
  }

  // --- Execution (Sprint 19 seam) ----------------------------------------
  //
  // The mock stores descriptions of runs and never executes one, so the
  // execution methods answer honestly: there is no engine here to launch.

  async execute(_id: string): Promise<TaskDetail> {
    await delay();
    throw new TaskError(
      "unavailable",
      "The offline mock can't run a workflow. Switch to the backend adapter."
    );
  }

  async executions(_id: string): Promise<WorkflowRunPage> {
    await delay();
    // No engine, no history — an empty page is the truth, and the screens
    // already render an honest empty state for it.
    return { items: [], total: 0 };
  }

  async retryExecution(_id: string, _executionId: string): Promise<TaskDetail> {
    await delay();
    throw new TaskError(
      "unavailable",
      "The offline mock can't run a workflow. Switch to the backend adapter."
    );
  }

  async queue(): Promise<QueueSnapshot> {
    await delay();
    const tasks = readTasks();

    // The fixture order comes first, then anything the user queued since, in the
    // position the adapter gave it. Ordering is carried, never invented here.
    const seeded = QUEUE_ORDER.map(({ taskId, position, estimatedOrder }) => {
      const task = tasks.find((t) => t.id === taskId);
      return task ? toQueueEntry(task, position, estimatedOrder) : null;
    }).filter((e): e is QueueEntry => e !== null && e.taskId !== undefined);

    const seededIds = new Set(seeded.map((e) => e.taskId));
    const added = tasks
      .filter((t) => t.state === "QUEUED" && !seededIds.has(t.id))
      .sort((a, b) => a.sequence - b.sequence)
      .map((task, i) => toQueueEntry(task, seeded.length + i + 1, "Queued by you"));

    const entries = [...seeded, ...added].map((entry, i) => ({ ...entry, position: i + 1 }));
    return { entries, waitingCount: entries.length };
  }
}

const toQueueEntry = (task: TaskDetail, position: number, estimatedOrder: string): QueueEntry => ({
  taskId: task.id,
  taskName: task.name,
  businessId: task.businessId,
  position,
  priority: task.priority,
  executionMode: task.executionMode,
  employeeName: task.assignee?.employeeName ?? "Unassigned",
  estimatedOrder,
});

/**
 * Names for the ids a stored mock task may reference.
 *
 * A task carries only a workflow/employee id and the name to show beside it;
 * the workflow and employee modules own the records themselves. The real
 * builder options come from those services (Sprint 19); these remain only so
 * the offline mock can resolve a display name without reaching into another
 * mock's fixtures.
 */
const WORKFLOW_NAMES: Record<string, string> = {
  wfl_1: "Weekly competitor brief",
  wfl_2: "Market signal digest",
  wfl_3: "Triage new issues",
  wfl_4: "Dependency upgrade sweep",
  wfl_5: "Release notes draft",
  wfl_6: "Monthly revenue rollup",
  wfl_7: "Churn cohort refresh",
  wfl_8: "Weekly planning prep",
  wfl_9: "Inbox triage",
  wfl_10: "Escalation handoff",
};

const EMPLOYEE_NAMES: Record<string, string> = {
  emp_1: "Atlas",
  emp_2: "Byte",
  emp_3: "Vera",
  emp_4: "Nova",
  emp_5: "Quill",
  emp_6: "Echo",
  emp_7: "Sage",
};
