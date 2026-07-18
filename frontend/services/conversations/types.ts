/**
 * Conversation domain contracts — provider-independent. The conversations
 * feature depends only on these types and the `ConversationsAdapter` interface,
 * never on a concrete provider. Sprint 17.9 ships a deterministic mock adapter;
 * the Sprint 5 backend adapter drops in later with zero changes to callers.
 *
 * ## What is real, and what this layer is projecting
 *
 * The Conversation Engine is **built** (Sprint 5). Its contract is small and
 * exact, and every backend-mirrored field below keeps its spelling:
 *
 *     Conversation = { id, employee_id, title, status, created_at, updated_at }
 *     status ∈ { active, archived }        (app/utils/constants.ConversationStatus)
 *     Message = { id, conversation_id, role, content, created_at }   — immutable
 *     role ∈ { user, assistant, system }   (app/utils/constants.MessageRole)
 *
 * Everything beyond those fields — message kinds, attachments, approvals,
 * artifacts, references, participants, tags, pins, unread counts, sharing,
 * suggestions — has **no column behind it today**. Each is marked as projection
 * so Sprint 18 knows exactly what binds to the wire and what must first be
 * decided. Nothing here calls an LLM, executes a workflow, or synthesises
 * speech; replies come from fixtures and are claims about shape, not behaviour.
 */

import type { ApprovalStatus, StatusTone } from "@/types/domain";

// =====================================================================
// Backend-mirrored vocabulary
// =====================================================================

/**
 * **Backend contract.** Mirrors `app/utils/constants.ConversationStatus`
 * exactly, lowercase values and all. It lives here rather than `types/domain.ts`
 * for the same reason `MEMORY_TYPES` lives in `services/memory/types.ts`: that
 * file mirrors `backend/app/services/ai_employee/*`, and this enum is from
 * `app/utils`.
 */
export const CONVERSATION_STATUSES = ["active", "archived"] as const;
export type ConversationStatus = (typeof CONVERSATION_STATUSES)[number];

export const CONVERSATION_STATUS_LABEL: Record<ConversationStatus, string> = {
  active: "Active",
  archived: "Archived",
};

/** Active is in use (info); archived is settled and out of the way (neutral). */
export const CONVERSATION_STATUS_TONE: Record<ConversationStatus, StatusTone> = {
  active: "info",
  archived: "neutral",
};

/**
 * **Backend contract.** Mirrors `app/utils/constants.MessageRole` exactly.
 * `user` is the human, `assistant` is the AI employee, `system` is the platform
 * speaking about the conversation.
 */
export const MESSAGE_ROLES = ["user", "assistant", "system"] as const;
export type MessageRole = (typeof MESSAGE_ROLES)[number];

export const MESSAGE_ROLE_LABEL: Record<MessageRole, string> = {
  user: "You",
  assistant: "AI employee",
  system: "System",
};

// =====================================================================
// Projected vocabulary (no backend column yet)
// =====================================================================

/**
 * **Projection.** What a message *carries*. The backend stores free `content`
 * and a `role`, nothing about form — so this is a rendering directive authored
 * by fixtures, not a wire field. Sprint 18 has to decide where it lives
 * (structured content, metadata, or a new column). `text` is the plain case;
 * every other kind renders as a card inside the thread.
 */
export const MESSAGE_KINDS = [
  "text",
  "approval_request",
  "artifact",
  "workflow_reference",
  "task_reference",
  "memory_reference",
  "notification",
] as const;
export type MessageKind = (typeof MESSAGE_KINDS)[number];

/**
 * **Projection.** Delivery standing for the read receipts column of the thread.
 * Purely visual — the backend has no delivery tracking.
 */
export const READ_STATUSES = ["sending", "sent", "read"] as const;
export type ReadStatus = (typeof READ_STATUSES)[number];

export const READ_STATUS_LABEL: Record<ReadStatus, string> = {
  sending: "Sending",
  sent: "Sent",
  read: "Read",
};

/**
 * **Projection.** What an attachment is. Mock preview only — nothing uploads,
 * parses, or opens.
 */
export const ATTACHMENT_KINDS = [
  "document",
  "image",
  "code",
  "report",
  "workflow",
  "task",
  "memory",
  "artifact",
] as const;
export type AttachmentKind = (typeof ATTACHMENT_KINDS)[number];

export const ATTACHMENT_KIND_LABEL: Record<AttachmentKind, string> = {
  document: "Document",
  image: "Image",
  code: "Code",
  report: "Report",
  workflow: "Workflow",
  task: "Task",
  memory: "Memory",
  artifact: "Artifact",
};

/**
 * **Projection.** What a generated artifact is. Named to read alongside
 * `services/tasks` `ARTIFACT_KINDS`, plus the conversation-native kinds
 * (workflow drafts and summaries) the composer can ask for.
 */
export const CONVERSATION_ARTIFACT_KINDS = ["document", "code", "report", "workflow", "summary"] as const;
export type ConversationArtifactKind = (typeof CONVERSATION_ARTIFACT_KINDS)[number];

export const CONVERSATION_ARTIFACT_KIND_LABEL: Record<ConversationArtifactKind, string> = {
  document: "Document",
  code: "Code",
  report: "Report",
  workflow: "Workflow",
  summary: "Summary",
};

// =====================================================================
// References — identity only; the owning module owns the rest
// =====================================================================

/** Who a conversation is with. Identity only — the employee module owns the rest. */
export interface EmployeeRef {
  employeeId: string;
  employeeName: string;
  /** One line on what this employee does, for the context panel. */
  roleTitle: string;
}

export interface WorkflowRef {
  workflowId: string;
  workflowName: string;
}

export interface TaskRef {
  taskId: string;
  /** The id a person quotes — the backend's own `task_id`. */
  businessId: string;
  taskName: string;
}

export interface MemoryRef {
  memoryId: string;
  title: string;
}

// =====================================================================
// Message payloads (projection)
// =====================================================================

/** What an `approval_request` message carries. UI only — deciding moves no run. */
export interface ApprovalPayload {
  approvalId: string;
  title: string;
  description: string;
  status: ApprovalStatus;
  /** The reviewer's note, once there is one. */
  comment: string | null;
}

/** What an `artifact` message carries. Mock preview only. */
export interface ArtifactPayload {
  artifactId: string;
  kind: ConversationArtifactKind;
  name: string;
  /** Human-readable size, carried from fixtures — never computed here. */
  size: string;
  /** Inline preview text; `null` when there is nothing to show inline. */
  preview: string | null;
}

/** What a `notification` message carries. */
export interface NotificationPayload {
  tone: StatusTone;
  headline: string;
}

/** An attachment on a message or staged in the composer. Mock only. */
export interface Attachment {
  id: string;
  kind: AttachmentKind;
  name: string;
  size: string;
  /** One-line mock preview; `null` when the kind has nothing inline. */
  preview: string | null;
}

// =====================================================================
// Message
// =====================================================================

/**
 * A message in a conversation's chronological history. `id`, `conversationId`,
 * `role`, `content` and `createdAt` mirror the backend's `MessageResponse`;
 * everything after them is projection. Messages are immutable, as the backend's
 * are — the mock never edits one in place.
 */
export interface ConversationMessage {
  id: string;
  conversationId: string;
  role: MessageRole;
  content: string;
  /** ISO timestamp, fixture-pinned — formatted through `utils/format` only. */
  createdAt: string;
  // ---- projection from here down ----
  kind: MessageKind;
  readStatus: ReadStatus;
  attachments: Attachment[];
  /** Present only when `kind` is `approval_request`. */
  approval: ApprovalPayload | null;
  /** Present only when `kind` is `artifact`. */
  artifact: ArtifactPayload | null;
  /** Present only when `kind` is `workflow_reference`. */
  workflowRef: WorkflowRef | null;
  /** Present only when `kind` is `task_reference`. */
  taskRef: TaskRef | null;
  /** Present only when `kind` is `memory_reference`. */
  memoryRef: MemoryRef | null;
  /** Present only when `kind` is `notification`. */
  notification: NotificationPayload | null;
}

// =====================================================================
// Conversation
// =====================================================================

/** **Projection.** Who is in the room. */
export interface Participant {
  id: string;
  name: string;
  /** `user` for the human; `assistant` for an AI employee. */
  role: Extract<MessageRole, "user" | "assistant">;
  /** One line under the name — a role title or "Workspace owner". */
  detail: string;
}

/** **Projection.** Something pinned to the context panel. */
export interface PinnedItem {
  id: string;
  label: string;
  /** What the pin points at — resolves the icon and the link. */
  kind: Extract<AttachmentKind, "workflow" | "task" | "memory" | "artifact" | "document">;
  href: string | null;
}

/** What the sidebar list needs. */
export interface ConversationSummary {
  id: string;
  /** Backend `employee_id`, denormalized with its display identity. */
  employee: EmployeeRef;
  title: string;
  status: ConversationStatus;
  createdAt: string;
  updatedAt: string;
  // ---- projection from here down ----
  /** One line of the latest message, for the list row. */
  lastMessagePreview: string;
  /** Carried, never counted here. `0` reads as caught up. */
  unreadCount: number;
  pinned: boolean;
  /** Visible to teammates on the shared screen. */
  shared: boolean;
  tags: string[];
}

/** Everything the workspace's context panel shows. */
export interface ConversationDetail extends ConversationSummary {
  participants: Participant[];
  /** Carried from fixtures, like every count in this app. */
  messageCount: number;
  referencedWorkflows: WorkflowRef[];
  referencedTasks: TaskRef[];
  referencedMemories: MemoryRef[];
  pinnedItems: PinnedItem[];
}

// =====================================================================
// Composer → adapter
// =====================================================================

/**
 * What the composer hands the adapter. Mirrors the backend's `MessageCreate`
 * (`role` is implied `user`, content trimmed and non-empty); attachments and
 * references ride alongside as projection.
 */
export interface OutgoingMessage {
  content: string;
  attachments: Attachment[];
}

/**
 * What a send returns: the stored user message and the employee's scripted
 * reply. Two messages, not a stream — the streaming *animation* is the UI's,
 * and nothing here generates anything.
 */
export interface SendReceipt {
  userMessage: ConversationMessage;
  assistantMessage: ConversationMessage;
}

/** What the UI sends when a reviewer decides an in-thread approval. */
export interface ConversationApprovalDecision {
  conversationId: string;
  messageId: string;
  status: Extract<ApprovalStatus, "APPROVED" | "REJECTED">;
  comment: string;
}

// =====================================================================
// Suggestions (projection)
// =====================================================================

export const SUGGESTION_KINDS = ["prompt", "task", "workflow", "memory", "employee", "action"] as const;
export type SuggestionKind = (typeof SUGGESTION_KINDS)[number];

export const SUGGESTION_KIND_LABEL: Record<SuggestionKind, string> = {
  prompt: "Suggested prompt",
  task: "Recent task",
  workflow: "Recent workflow",
  memory: "Recent memory",
  employee: "Recent employee",
  action: "Quick action",
};

/** A chip above the composer. Picking one only writes into the draft. */
export interface Suggestion {
  id: string;
  kind: SuggestionKind;
  label: string;
  /** What lands in the composer when picked. */
  insertText: string;
}

// =====================================================================
// Search
// =====================================================================

/** Which record a search query is scanning. */
export const SEARCH_SCOPES = [
  "conversations",
  "messages",
  "employees",
  "workflows",
  "tasks",
  "memories",
] as const;
export type SearchScope = (typeof SEARCH_SCOPES)[number];

export const SEARCH_SCOPE_LABEL: Record<SearchScope, string> = {
  conversations: "Conversations",
  messages: "Messages",
  employees: "AI employees",
  workflows: "Workflows",
  tasks: "Tasks",
  memories: "Memories",
};

/** `"ALL"` is the unset state for each facet — never a real value. */
export interface ConversationSearchQuery {
  keyword: string;
  scope: SearchScope | "ALL";
  employeeId: string | "ALL";
  status: ConversationStatus | "ALL";
  tag: string | "ALL";
  /** ISO days, inclusive. Empty string means unbounded. */
  fromDate: string;
  toDate: string;
}

export const EMPTY_SEARCH_QUERY: ConversationSearchQuery = {
  keyword: "",
  scope: "ALL",
  employeeId: "ALL",
  status: "ALL",
  tag: "ALL",
  fromDate: "",
  toDate: "",
};

/** One hit. `messageId` is `null` when the conversation itself matched. */
export interface ConversationSearchResult {
  id: string;
  conversationId: string;
  conversationTitle: string;
  employeeName: string;
  messageId: string | null;
  /** Where the term was found, in the scope vocabulary. */
  matchedIn: SearchScope;
  /** The matching line, verbatim from the record. */
  snippet: string;
  createdAt: string;
}

// =====================================================================
// Errors & the adapter seam
// =====================================================================

export type ConversationErrorCode = "not_found" | "invalid_message" | "conversation_archived" | "unknown";

export class ConversationError extends Error {
  code: ConversationErrorCode;
  constructor(code: ConversationErrorCode, message: string) {
    super(message);
    this.name = "ConversationError";
    this.code = code;
  }
}

/** What a create hands the adapter — the backend's `ConversationCreate` plus the owner employee. */
export interface ConversationDraft {
  title: string;
  employeeId: string;
}

/**
 * The single seam every conversation backend must implement. Shaped after the
 * Sprint 5 API: `list`/`detail`/`rename`/`setStatus` are conversation CRUD,
 * `messages`/`send` are the message endpoints, and the rest are projection this
 * sprint owns until the backend grows a column for them.
 */
export interface ConversationsAdapter {
  list(): Promise<ConversationSummary[]>;
  detail(id: string): Promise<ConversationDetail>;
  create(draft: ConversationDraft): Promise<ConversationDetail>;
  rename(id: string, title: string): Promise<ConversationDetail>;
  /** Mirrors the backend's `ConversationUpdate.status` — archive and restore. */
  setStatus(id: string, status: ConversationStatus): Promise<ConversationDetail>;
  messages(id: string): Promise<ConversationMessage[]>;
  /** Appends the user message and the employee's scripted reply. */
  send(id: string, outgoing: OutgoingMessage): Promise<SendReceipt>;
  togglePinned(id: string): Promise<ConversationSummary>;
  markRead(id: string): Promise<ConversationSummary>;
  setShared(id: string, shared: boolean): Promise<ConversationSummary>;
  decide(decision: ConversationApprovalDecision): Promise<ConversationMessage>;
  search(query: ConversationSearchQuery): Promise<ConversationSearchResult[]>;
  /** Chips for the composer; `id` scopes them to a conversation when given. */
  suggestions(id: string | null): Promise<Suggestion[]>;
}
