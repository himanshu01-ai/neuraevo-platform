/**
 * Backend ⇄ frontend translation for conversations (Sprint 21).
 *
 * The one place the FastAPI Conversation Hub vocabulary is spoken. Above the
 * adapter, callers see only the domain model in `types.ts`.
 *
 * The backend contract is small and exact — a conversation's real columns plus
 * the owning employee, and a message's `role`/`content`/`channel`. Everything
 * the workspace shows beyond that (message kinds, attachments, references,
 * pins, unread, sharing, tags, participants) has no column behind it yet, so
 * these mappers fill each projected field with a stable default. Nothing is
 * fabricated as if real: the projections are the same the mock declared, moved
 * behind the seam so the workspace renders on live data.
 */

import { z } from "zod";
import type {
  ConversationDetail,
  ConversationMessage,
  ConversationStatus,
  ConversationSummary,
  MessageChannel,
  MessageRole,
} from "./types";

// --- Wire schemas (mirror app/schemas/conversation_hub + message) -------

export const conversationSummarySchema = z.object({
  id: z.string(),
  employee_id: z.string(),
  employee_name: z.string(),
  title: z.string(),
  status: z.enum(["active", "archived"]),
  message_count: z.number(),
  last_message: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const conversationListSchema = z.object({
  items: z.array(conversationSummarySchema),
  total: z.number(),
});

export const messageSchema = z.object({
  id: z.string(),
  conversation_id: z.string(),
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
  channel: z.enum(["text", "voice"]),
  created_at: z.string(),
});

export const turnSchema = z.object({
  user_message: messageSchema,
  assistant_message: messageSchema,
});

export type ConversationSummaryWire = z.infer<typeof conversationSummarySchema>;
export type MessageWire = z.infer<typeof messageSchema>;

// --- Mappers ------------------------------------------------------------

export function toConversationSummary(raw: ConversationSummaryWire): ConversationSummary {
  return {
    id: raw.id,
    employee: {
      employeeId: raw.employee_id,
      employeeName: raw.employee_name,
      roleTitle: "",
    },
    title: raw.title,
    status: raw.status as ConversationStatus,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    // ---- projection: no backend column yet ----
    lastMessagePreview: raw.last_message ?? "",
    unreadCount: 0,
    pinned: false,
    shared: false,
    tags: [],
  };
}

export function toConversationDetail(raw: ConversationSummaryWire): ConversationDetail {
  return {
    ...toConversationSummary(raw),
    // The one participant the backend knows: the employee the conversation is
    // with. The human is implicit in every thread.
    participants: [
      {
        id: raw.employee_id,
        name: raw.employee_name,
        role: "assistant",
        detail: "",
      },
    ],
    messageCount: raw.message_count,
    // ---- projection: no backend relation yet ----
    referencedWorkflows: [],
    referencedTasks: [],
    referencedMemories: [],
    pinnedItems: [],
  };
}

export function toConversationMessage(raw: MessageWire): ConversationMessage {
  return {
    id: raw.id,
    conversationId: raw.conversation_id,
    role: raw.role as MessageRole,
    content: raw.content,
    channel: raw.channel as MessageChannel,
    createdAt: raw.created_at,
    // ---- projection: plain text; the workspace's rich kinds have no column ----
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
}
