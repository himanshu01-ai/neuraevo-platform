import { MockConversationsAdapter } from "./mock-adapter";
import type {
  ConversationApprovalDecision,
  ConversationDraft,
  ConversationSearchQuery,
  ConversationStatus,
  ConversationsAdapter,
  OutgoingMessage,
} from "./types";

/**
 * The app's single entry point to conversation data. Swapping providers =
 * swapping this one adapter for the Sprint 5 backend adapter; callers (the
 * feature hooks) never change. No fetch/axios/SDKs.
 */
const adapter: ConversationsAdapter = new MockConversationsAdapter();

export const conversationService = {
  list: () => adapter.list(),
  detail: (id: string) => adapter.detail(id),
  create: (draft: ConversationDraft) => adapter.create(draft),
  rename: (id: string, title: string) => adapter.rename(id, title),
  setStatus: (id: string, status: ConversationStatus) => adapter.setStatus(id, status),
  messages: (id: string) => adapter.messages(id),
  send: (id: string, outgoing: OutgoingMessage) => adapter.send(id, outgoing),
  togglePinned: (id: string) => adapter.togglePinned(id),
  markRead: (id: string) => adapter.markRead(id),
  setShared: (id: string, shared: boolean) => adapter.setShared(id, shared),
  decide: (decision: ConversationApprovalDecision) => adapter.decide(decision),
  search: (query: ConversationSearchQuery) => adapter.search(query),
  suggestions: (id: string | null) => adapter.suggestions(id),
};

export type ConversationService = typeof conversationService;
