import { env } from "@/lib/env";
import { BackendConversationsAdapter } from "./backend-adapter";
import { MockConversationsAdapter } from "./mock-adapter";
import type {
  ConversationActionInput,
  ConversationApprovalDecision,
  ConversationDraft,
  ConversationSearchQuery,
  ConversationStatus,
  ConversationsAdapter,
  OutgoingMessage,
} from "./types";

/**
 * The app's single entry point to conversation data, and the only place that
 * knows which adapter is active. Callers (the feature hooks) never import an
 * adapter.
 *
 * Sprint 21 swapped the default from the Sprint 17.9 mock to the real FastAPI
 * Conversation Hub — text and voice both run through it. The mock stays
 * selectable via `NEXT_PUBLIC_CONVERSATIONS_ADAPTER=mock` for offline UI work;
 * the choice is app-wide, so mock and real conversations are never mixed.
 */
const adapter: ConversationsAdapter =
  env.NEXT_PUBLIC_CONVERSATIONS_ADAPTER === "mock"
    ? new MockConversationsAdapter()
    : new BackendConversationsAdapter();

export const conversationService = {
  list: () => adapter.list(),
  detail: (id: string) => adapter.detail(id),
  create: (draft: ConversationDraft) => adapter.create(draft),
  rename: (id: string, title: string) => adapter.rename(id, title),
  setStatus: (id: string, status: ConversationStatus) => adapter.setStatus(id, status),
  messages: (id: string) => adapter.messages(id),
  send: (id: string, outgoing: OutgoingMessage) => adapter.send(id, outgoing),
  createAction: (id: string, action: ConversationActionInput) =>
    adapter.createAction(id, action),
  togglePinned: (id: string) => adapter.togglePinned(id),
  markRead: (id: string) => adapter.markRead(id),
  setShared: (id: string, shared: boolean) => adapter.setShared(id, shared),
  decide: (decision: ConversationApprovalDecision) => adapter.decide(decision),
  search: (query: ConversationSearchQuery) => adapter.search(query),
  suggestions: (id: string | null) => adapter.suggestions(id),
};

export type ConversationService = typeof conversationService;
