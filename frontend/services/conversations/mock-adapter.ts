import { dateValue, isoDay } from "@/utils/format";
import {
  CONVERSATIONS,
  CONVERSATION_SUGGESTIONS,
  FALLBACK_REPLY,
  GLOBAL_SUGGESTIONS,
  MESSAGES_BY_CONVERSATION,
  SCRIPTED_REPLIES,
} from "./fixtures";
import {
  ConversationError,
  type ConversationActionInput,
  type ConversationActionReceipt,
  type ConversationApprovalDecision,
  type ConversationDetail,
  type ConversationDraft,
  type ConversationMessage,
  type ConversationSearchQuery,
  type ConversationSearchResult,
  type ConversationStatus,
  type ConversationSummary,
  type ConversationsAdapter,
  type OutgoingMessage,
  type SendReceipt,
  type Suggestion,
} from "./types";
import { EMPLOYEE_LIST } from "./fixtures";

/**
 * Deterministic in-browser mock of the Sprint 5 Conversation Engine. No
 * network, no LLM, no speech, no randomness. Writes go to localStorage so a
 * sent message survives a reload — the same approach `MockTasksAdapter` (17.7)
 * and the rest of the app's mocks use.
 *
 * ## What "mock reply" means here
 *
 * `send` appends the user's message and then the employee's *scripted* reply,
 * cycled from `SCRIPTED_REPLIES` by how many user messages the thread already
 * holds. The same send always meets the same reply; nothing generates. The
 * typing indicator and streaming reveal in the UI are animation over these
 * fixtures, not evidence of a model.
 *
 * ## No clock reads
 *
 * New messages need a `createdAt`, and this file never calls `Date.now()`:
 * a new timestamp is the previous message's plus one minute. Time here is a
 * function of state, so the same actions always produce the same bytes.
 */

const CONVERSATIONS_KEY = "neuraevo.mock.conversations";
const MESSAGES_KEY = "neuraevo.mock.conversations.messages";
const LATENCY_MS = 350;
/** The scripted reply lands after the typing indicator has had a beat. */
const REPLY_LATENCY_MS = 900;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

/** Structured clone via JSON — fixtures and stored rows are plain data. */
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

type MessageLog = Record<string, ConversationMessage[]>;

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

const readConversations = (): ConversationDetail[] => {
  const rows = read<ConversationDetail[]>(CONVERSATIONS_KEY, () => copy(CONVERSATIONS));
  return Array.isArray(rows) ? rows : copy(CONVERSATIONS);
};
const writeConversations = (rows: ConversationDetail[]) => write(CONVERSATIONS_KEY, rows);

const readMessages = (): MessageLog => read<MessageLog>(MESSAGES_KEY, () => copy(MESSAGES_BY_CONVERSATION));
const writeMessages = (log: MessageLog) => write(MESSAGES_KEY, log);

const toSummary = (row: ConversationDetail): ConversationSummary => ({
  id: row.id,
  employee: row.employee,
  title: row.title,
  status: row.status,
  createdAt: row.createdAt,
  updatedAt: row.updatedAt,
  lastMessagePreview: row.lastMessagePreview,
  unreadCount: row.unreadCount,
  pinned: row.pinned,
  shared: row.shared,
  tags: row.tags,
});

/** Deterministic id from the existing rows — no randomness, no timestamps. */
function nextId(rows: { id: string }[], prefix: string): string {
  let n = rows.length + 1;
  while (rows.some((r) => r.id === `${prefix}_${n}`)) n++;
  return `${prefix}_${n}`;
}

/** The previous message's moment plus one minute — never a clock read. */
function nextTimestamp(messages: ConversationMessage[], fallback: string): string {
  const last = messages[messages.length - 1];
  const base = last ? dateValue(last.createdAt) : dateValue(fallback);
  return new Date(base + 60_000).toISOString();
}

function findConversation(rows: ConversationDetail[], id: string): { row: ConversationDetail; index: number } {
  const index = rows.findIndex((r) => r.id === id);
  const row = index >= 0 ? rows[index] : undefined;
  if (!row) throw new ConversationError("not_found", "That conversation doesn't exist.");
  return { row, index };
}

/** One line of a message for list rows — first line, elided when long. */
function preview(content: string): string {
  const line = (content.split("\n")[0] ?? "").trim();
  return line.length > 80 ? `${line.slice(0, 79)}…` : line;
}

export class MockConversationsAdapter implements ConversationsAdapter {
  async list(): Promise<ConversationSummary[]> {
    await delay();
    return readConversations().map(toSummary);
  }

  async detail(id: string): Promise<ConversationDetail> {
    await delay();
    const { row } = findConversation(readConversations(), id);
    return copy(row);
  }

  async create(draft: ConversationDraft): Promise<ConversationDetail> {
    await delay();
    const title = draft.title.trim();
    if (!title) throw new ConversationError("invalid_message", "A conversation needs a title.");
    const employee = EMPLOYEE_LIST.find((e) => e.employeeId === draft.employeeId);
    if (!employee) throw new ConversationError("not_found", "That AI employee doesn't exist.");

    const rows = readConversations();
    const id = nextId(rows, "conv");
    // A new conversation starts just after the newest activity in the store —
    // deterministic, and always sorts to the top.
    const newest = rows.reduce((max, r) => Math.max(max, dateValue(r.updatedAt)), 0);
    const createdAt = new Date(newest + 60_000).toISOString();

    const row: ConversationDetail = {
      id,
      employee,
      title,
      status: "active",
      createdAt,
      updatedAt: createdAt,
      lastMessagePreview: "No messages yet.",
      unreadCount: 0,
      pinned: false,
      shared: false,
      tags: [],
      participants: [
        { id: "user_1", name: "Himanshu", role: "user", detail: "Workspace owner" },
        { id: employee.employeeId, name: employee.employeeName, role: "assistant", detail: employee.roleTitle },
      ],
      messageCount: 0,
      referencedWorkflows: [],
      referencedTasks: [],
      referencedMemories: [],
      pinnedItems: [],
    };

    writeConversations([row, ...rows]);
    const log = readMessages();
    log[id] = [];
    writeMessages(log);
    return copy(row);
  }

  async rename(id: string, title: string): Promise<ConversationDetail> {
    await delay();
    const trimmed = title.trim();
    if (!trimmed) throw new ConversationError("invalid_message", "A conversation needs a title.");
    const rows = readConversations();
    const { row, index } = findConversation(rows, id);
    const next = { ...row, title: trimmed };
    rows[index] = next;
    writeConversations(rows);
    return copy(next);
  }

  async setStatus(id: string, status: ConversationStatus): Promise<ConversationDetail> {
    await delay();
    const rows = readConversations();
    const { row, index } = findConversation(rows, id);
    const next = { ...row, status };
    rows[index] = next;
    writeConversations(rows);
    return copy(next);
  }

  async messages(id: string): Promise<ConversationMessage[]> {
    await delay();
    findConversation(readConversations(), id);
    // Chronological, as the backend orders them (`order_by="Message.created_at"`).
    return copy(readMessages()[id] ?? []).sort((a, b) => dateValue(a.createdAt) - dateValue(b.createdAt));
  }

  async send(id: string, outgoing: OutgoingMessage): Promise<SendReceipt> {
    await delay();
    const content = outgoing.content.trim();
    // Mirrors the backend's MessageContent constraint: trimmed, non-empty.
    if (!content) throw new ConversationError("invalid_message", "A message needs some content.");

    const rows = readConversations();
    const { row, index } = findConversation(rows, id);
    if (row.status === "archived")
      throw new ConversationError("conversation_archived", "This conversation is archived. Restore it to continue.");

    const log = readMessages();
    const thread = log[id] ?? [];

    const userMessage: ConversationMessage = {
      id: `${id}_m${thread.length + 1}`,
      conversationId: id,
      role: "user",
      content,
      channel: outgoing.channel ?? "text",
      createdAt: nextTimestamp(thread, row.createdAt),
      kind: "text",
      readStatus: "sent",
      attachments: copy(outgoing.attachments),
      approval: null,
      artifact: null,
      workflowRef: null,
      taskRef: null,
      memoryRef: null,
      notification: null,
    };

    // The reply script advances with each user message — same send, same reply.
    const script = SCRIPTED_REPLIES[id] ?? [];
    const userTurns = thread.filter((m) => m.role === "user").length;
    const replyText = script[userTurns % Math.max(script.length, 1)] ?? FALLBACK_REPLY;

    const withUser = [...thread, userMessage];
    const assistantMessage: ConversationMessage = {
      id: `${id}_m${withUser.length + 1}`,
      conversationId: id,
      role: "assistant",
      content: replyText,
      channel: outgoing.channel ?? "text",
      createdAt: nextTimestamp(withUser, row.createdAt),
      kind: "text",
      readStatus: "read",
      attachments: [],
      approval: null,
      artifact: null,
      workflowRef: null,
      taskRef: null,
      memoryRef: null,
      notification: null,
    };

    log[id] = [...withUser, assistantMessage];
    writeMessages(log);

    rows[index] = {
      ...row,
      updatedAt: assistantMessage.createdAt,
      lastMessagePreview: preview(assistantMessage.content),
      messageCount: log[id].length,
      unreadCount: 0,
    };
    writeConversations(rows);

    // The pause between the user's message landing and the reply arriving —
    // the window the typing indicator fills. Animation timing, not generation.
    await delay(REPLY_LATENCY_MS);
    return { userMessage: copy(userMessage), assistantMessage: copy(assistantMessage) };
  }

  /**
   * Carry out a confirmed action. Offline, this synthesises the task receipt the
   * backend would return — no task store to write to here — so the voice
   * approval flow stays exercisable in the mock. The real linking, activity, and
   * notification are the backend adapter's.
   */
  async createAction(
    id: string,
    action: ConversationActionInput
  ): Promise<ConversationActionReceipt> {
    await delay();
    const rows = readConversations();
    findConversation(rows, id); // asserts the conversation exists (throws if not)
    const name = `${action.label.trim()}: ${action.summary.trim()}`.replace(/^:\s*|\s*:$/g, "").trim();
    return {
      taskId: `tsk_${id}_${Date.now()}`,
      businessId: "TSK-preview",
      name: name || action.label.trim(),
      status: "pending",
    };
  }

  async togglePinned(id: string): Promise<ConversationSummary> {
    await delay();
    const rows = readConversations();
    const { row, index } = findConversation(rows, id);
    const next = { ...row, pinned: !row.pinned };
    rows[index] = next;
    writeConversations(rows);
    return toSummary(copy(next));
  }

  async markRead(id: string): Promise<ConversationSummary> {
    await delay();
    const rows = readConversations();
    const { row, index } = findConversation(rows, id);
    if (row.unreadCount === 0) return toSummary(copy(row));
    const next = { ...row, unreadCount: 0 };
    rows[index] = next;
    writeConversations(rows);
    return toSummary(copy(next));
  }

  async setShared(id: string, shared: boolean): Promise<ConversationSummary> {
    await delay();
    const rows = readConversations();
    const { row, index } = findConversation(rows, id);
    const next = { ...row, shared };
    rows[index] = next;
    writeConversations(rows);
    return toSummary(copy(next));
  }

  async decide(decision: ConversationApprovalDecision): Promise<ConversationMessage> {
    await delay();
    const log = readMessages();
    const thread = log[decision.conversationId] ?? [];
    const index = thread.findIndex((m) => m.id === decision.messageId);
    const message = index >= 0 ? thread[index] : undefined;
    if (!message || !message.approval)
      throw new ConversationError("not_found", "That approval doesn't exist.");
    if (message.approval.status !== "PENDING")
      throw new ConversationError("invalid_message", "That approval has already been decided.");

    // Messages are immutable in the backend; the approval payload is projection,
    // so the decision lands there and only there.
    const next: ConversationMessage = {
      ...message,
      approval: {
        ...message.approval,
        status: decision.status,
        comment: decision.comment.trim() || null,
      },
    };
    thread[index] = next;
    log[decision.conversationId] = thread;
    writeMessages(log);
    return copy(next);
  }

  /**
   * Filtering only — every facet is an exact match except `keyword`, which is a
   * plain substring scan. Nothing is ranked; results come back newest first.
   * The same call, aimed at the backend, is where relevance would live.
   */
  async search(query: ConversationSearchQuery): Promise<ConversationSearchResult[]> {
    await delay();
    const term = query.keyword.trim().toLowerCase();
    const results: ConversationSearchResult[] = [];
    const rows = readConversations();
    const log = readMessages();

    for (const row of rows) {
      if (query.employeeId !== "ALL" && row.employee.employeeId !== query.employeeId) continue;
      if (query.status !== "ALL" && row.status !== query.status) continue;
      if (query.tag !== "ALL" && !row.tags.includes(query.tag)) continue;

      const inRange = (iso: string) => {
        const day = isoDay(iso);
        if (query.fromDate && day < query.fromDate) return false;
        if (query.toDate && day > query.toDate) return false;
        return true;
      };

      const wantConversations = query.scope === "ALL" || query.scope === "conversations";
      const wantEmployees = query.scope === "ALL" || query.scope === "employees";
      const wantMessages = query.scope === "ALL" || query.scope === "messages";
      const wantWorkflows = query.scope === "ALL" || query.scope === "workflows";
      const wantTasks = query.scope === "ALL" || query.scope === "tasks";
      const wantMemories = query.scope === "ALL" || query.scope === "memories";

      const base = {
        conversationId: row.id,
        conversationTitle: row.title,
        employeeName: row.employee.employeeName,
      };

      if (wantConversations && inRange(row.updatedAt) && (!term || row.title.toLowerCase().includes(term) || row.tags.some((t) => t.includes(term)))) {
        results.push({ ...base, id: `sr_${row.id}`, messageId: null, matchedIn: "conversations", snippet: row.lastMessagePreview, createdAt: row.updatedAt });
      }
      if (wantEmployees && term && row.employee.employeeName.toLowerCase().includes(term) && inRange(row.updatedAt)) {
        results.push({ ...base, id: `sr_${row.id}_emp`, messageId: null, matchedIn: "employees", snippet: `${row.employee.employeeName} — ${row.employee.roleTitle}`, createdAt: row.updatedAt });
      }

      for (const message of log[row.id] ?? []) {
        if (!inRange(message.createdAt)) continue;
        const hit = (text: string) => !term || text.toLowerCase().includes(term);

        if (wantMessages && message.kind === "text" && hit(message.content)) {
          results.push({ ...base, id: `sr_${message.id}`, messageId: message.id, matchedIn: "messages", snippet: preview(message.content), createdAt: message.createdAt });
        }
        if (wantWorkflows && message.workflowRef && hit(message.workflowRef.workflowName)) {
          results.push({ ...base, id: `sr_${message.id}_wf`, messageId: message.id, matchedIn: "workflows", snippet: message.workflowRef.workflowName, createdAt: message.createdAt });
        }
        if (wantTasks && message.taskRef && hit(`${message.taskRef.taskName} ${message.taskRef.businessId}`)) {
          results.push({ ...base, id: `sr_${message.id}_tk`, messageId: message.id, matchedIn: "tasks", snippet: `${message.taskRef.businessId} — ${message.taskRef.taskName}`, createdAt: message.createdAt });
        }
        if (wantMemories && message.memoryRef && hit(message.memoryRef.title)) {
          results.push({ ...base, id: `sr_${message.id}_mem`, messageId: message.id, matchedIn: "memories", snippet: message.memoryRef.title, createdAt: message.createdAt });
        }
      }
    }

    return results.sort((a, b) => dateValue(b.createdAt) - dateValue(a.createdAt));
  }

  async suggestions(id: string | null): Promise<Suggestion[]> {
    await delay();
    const scoped = id ? (CONVERSATION_SUGGESTIONS[id] ?? []) : [];
    return copy([...scoped, ...GLOBAL_SUGGESTIONS]);
  }
}
