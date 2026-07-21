import { z } from "zod";
import { ApiError, request } from "../http";
import { isoDay } from "@/utils/format";
import {
  conversationListSchema,
  conversationSummarySchema,
  messageSchema,
  toConversationDetail,
  toConversationMessage,
  toConversationSummary,
  turnSchema,
} from "./mapping";
import {
  ConversationError,
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

/**
 * Real conversation adapter, backed by the FastAPI Conversation Hub. Implements
 * the same `ConversationsAdapter` seam as the mock, so no caller changes.
 *
 *   GET    /conversations                     list (across employees)
 *   POST   /conversations                     create (with an employee)
 *   GET    /conversations/{id}                detail
 *   PATCH  /conversations/{id}                rename / archive / restore
 *   DELETE /conversations/{id}                delete
 *   GET    /conversations/{id}/messages       the transcript (text + voice)
 *   POST   /conversations/{id}/turn           one exchange → both messages
 *
 * Ownership and auth are the backend's; `services/http.ts` attaches and
 * refreshes the token. A turn carries the channel (`text`/`voice`) so a spoken
 * exchange is persisted as one; speech recognition and synthesis are the
 * browser's, at the edge.
 *
 * The workspace's projected surface (pins, sharing, unread, in-thread
 * approvals, suggestions) has no backend yet, so those methods answer honestly
 * — a no-op that returns the current record, or an empty result — rather than
 * pretending. Search is a client-side scan of the conversation list, which is
 * the one scope the hub can answer today.
 */

function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new ConversationError("unknown", "The server returned an unexpected response.");
  }
  return result.data;
}

/** Map a transport-level `ApiError` onto the conversation domain's vocabulary. */
function toConversationError(error: unknown, fallback: string): ConversationError {
  if (error instanceof ConversationError) return error;
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return new ConversationError("not_found", "That conversation doesn't exist.");
    }
    // 422 is a rejected message/body; a list `detail` is FastAPI rejecting the
    // request shape and tells a user nothing actionable.
    if (error.status === 422) {
      return Array.isArray(error.details)
        ? new ConversationError("unknown", fallback)
        : new ConversationError("invalid_message", error.message);
    }
    // 502/504 are the AI provider failing to reply; the message was saved.
    if (error.status === 502 || error.status === 504) {
      return new ConversationError("unknown", error.message);
    }
    return new ConversationError("unknown", error.message);
  }
  return new ConversationError("unknown", fallback);
}

export class BackendConversationsAdapter implements ConversationsAdapter {
  // --- Reads -------------------------------------------------------------

  async list(): Promise<ConversationSummary[]> {
    try {
      const raw = await request<unknown>("/conversations");
      return parseOrThrow(conversationListSchema, raw).items.map(toConversationSummary);
    } catch (error) {
      throw toConversationError(error, "Your conversations couldn't be loaded.");
    }
  }

  async detail(id: string): Promise<ConversationDetail> {
    try {
      const raw = await request<unknown>(`/conversations/${encodeURIComponent(id)}`);
      return toConversationDetail(parseOrThrow(conversationSummarySchema, raw));
    } catch (error) {
      throw toConversationError(error, "That conversation couldn't be loaded.");
    }
  }

  async messages(id: string): Promise<ConversationMessage[]> {
    try {
      const raw = await request<unknown>(`/conversations/${encodeURIComponent(id)}/messages`);
      return parseOrThrow(z.array(messageSchema), raw).map(toConversationMessage);
    } catch (error) {
      throw toConversationError(error, "That conversation's messages couldn't be loaded.");
    }
  }

  // --- Writes ------------------------------------------------------------

  async create(draft: ConversationDraft): Promise<ConversationDetail> {
    if (!draft.title.trim()) {
      throw new ConversationError("invalid_message", "A conversation needs a title.");
    }
    try {
      const raw = await request<unknown>("/conversations", {
        method: "POST",
        body: { employee_id: draft.employeeId, title: draft.title.trim() },
      });
      return toConversationDetail(parseOrThrow(conversationSummarySchema, raw));
    } catch (error) {
      throw toConversationError(error, "That conversation couldn't be started.");
    }
  }

  async rename(id: string, title: string): Promise<ConversationDetail> {
    return this.patch(id, { title: title.trim() }, "That conversation couldn't be renamed.");
  }

  async setStatus(id: string, status: ConversationStatus): Promise<ConversationDetail> {
    return this.patch(id, { status }, "That conversation couldn't be updated.");
  }

  private async patch(
    id: string,
    body: Record<string, unknown>,
    fallback: string
  ): Promise<ConversationDetail> {
    try {
      const raw = await request<unknown>(`/conversations/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body,
      });
      return toConversationDetail(parseOrThrow(conversationSummarySchema, raw));
    } catch (error) {
      throw toConversationError(error, fallback);
    }
  }

  /**
   * One turn: the human message and the employee's reply, both on the turn's
   * channel. The backend persists both and grounds the reply in the employee's
   * blueprint and memory — the same generation pipeline a typed turn uses.
   */
  async send(id: string, outgoing: OutgoingMessage): Promise<SendReceipt> {
    if (!outgoing.content.trim()) {
      throw new ConversationError("invalid_message", "A message can't be empty.");
    }
    try {
      const raw = await request<unknown>(`/conversations/${encodeURIComponent(id)}/turn`, {
        method: "POST",
        body: { content: outgoing.content.trim(), channel: outgoing.channel ?? "text" },
      });
      const turn = parseOrThrow(turnSchema, raw);
      return {
        userMessage: toConversationMessage(turn.user_message),
        assistantMessage: toConversationMessage(turn.assistant_message),
      };
    } catch (error) {
      throw toConversationError(error, "That message couldn't be sent.");
    }
  }

  // --- Projection-only (no backend column yet) ---------------------------
  //
  // Pins, sharing, unread and in-thread approvals have no backend today. Rather
  // than pretend, these return the current record unchanged (a no-op) or an
  // honest empty — the same stance the tasks adapter takes with approvals.

  async togglePinned(id: string): Promise<ConversationSummary> {
    return this.summary(id);
  }

  async markRead(id: string): Promise<ConversationSummary> {
    return this.summary(id);
  }

  async setShared(id: string): Promise<ConversationSummary> {
    return this.summary(id);
  }

  private async summary(id: string): Promise<ConversationSummary> {
    try {
      const raw = await request<unknown>(`/conversations/${encodeURIComponent(id)}`);
      return toConversationSummary(parseOrThrow(conversationSummarySchema, raw));
    } catch (error) {
      throw toConversationError(error, "That conversation couldn't be loaded.");
    }
  }

  async decide(_decision: ConversationApprovalDecision): Promise<ConversationMessage> {
    throw new ConversationError(
      "unknown",
      "In-thread approvals aren't connected to the platform yet."
    );
  }

  async suggestions(_id: string | null): Promise<Suggestion[]> {
    return [];
  }

  /**
   * Search scans the conversation list for the `conversations` scope — the one
   * the hub can answer without a message-search index. Keyword, employee and
   * status narrow it; other scopes return nothing rather than a false match.
   */
  async search(query: ConversationSearchQuery): Promise<ConversationSearchResult[]> {
    if (query.scope !== "ALL" && query.scope !== "conversations") return [];
    const conversations = await this.list();
    const term = query.keyword.trim().toLowerCase();
    const from = query.fromDate || null;
    const to = query.toDate || null;

    return conversations
      .filter((conversation) => {
        if (query.employeeId !== "ALL" && conversation.employee.employeeId !== query.employeeId) {
          return false;
        }
        if (query.status !== "ALL" && conversation.status !== query.status) return false;
        const day = isoDay(conversation.updatedAt);
        if (from && day < from) return false;
        if (to && day > to) return false;
        if (!term) return true;
        return (
          conversation.title.toLowerCase().includes(term) ||
          conversation.lastMessagePreview.toLowerCase().includes(term)
        );
      })
      .map((conversation) => ({
        id: `search_${conversation.id}`,
        conversationId: conversation.id,
        conversationTitle: conversation.title,
        employeeName: conversation.employee.employeeName,
        messageId: null,
        matchedIn: "conversations" as const,
        snippet: conversation.lastMessagePreview || conversation.title,
        createdAt: conversation.updatedAt,
      }));
  }
}
