import type { ConversationSearchQuery } from "./types";

/**
 * Query keys for the conversations resource. Hierarchical so a mutation can
 * invalidate one conversation (`conversationKeys.detail(id)`), its thread
 * (`messages(id)`), or the whole list. Shapes follow the central query-key
 * convention (docs/09), so this table lifts into that factory unchanged.
 */
export const conversationKeys = {
  all: ["conversations"] as const,
  lists: ["conversations", "list"] as const,
  detail: (id: string) => ["conversations", "detail", id] as const,
  messages: (id: string) => ["conversations", "messages", id] as const,
  search: (query: ConversationSearchQuery) => ["conversations", "search", query] as const,
  suggestions: (id: string | null) => ["conversations", "suggestions", id ?? "global"] as const,
} as const;
