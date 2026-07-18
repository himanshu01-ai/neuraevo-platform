import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ConversationStatus } from "@/services/conversations";

/**
 * The conversation workspace's client state: which conversation and message are
 * selected, how the sidebar list is narrowed, and whether the context panel is
 * open.
 *
 * No server data lives here (docs/09) — threads stay in the Query cache and
 * this store holds only the questions the user is asking of them. The context
 * panel's visibility is the one durable preference, persisted the way
 * `sidebarCollapsed` is; a filter or a selection is a moment, not a setting,
 * and resets on reload.
 */

/** How the sidebar list is ordered. `recent` is the platform's `updated_at`. */
export const CONVERSATION_SORTS = ["recent", "name", "unread"] as const;
export type ConversationSort = (typeof CONVERSATION_SORTS)[number];

export const CONVERSATION_SORT_LABEL: Record<ConversationSort, string> = {
  recent: "Most recent",
  name: "Name",
  unread: "Unread first",
};

/** Which section the context panel is showing. */
export type ContextPanelTab = "context" | "participants" | "pinned";

/** `"ALL"` is the unset state for each facet — never a real value. */
export interface ConversationFilters {
  search: string;
  status: ConversationStatus | "ALL";
  employeeId: string | "ALL";
  tag: string | "ALL";
  unreadOnly: boolean;
  pinnedOnly: boolean;
}

export const EMPTY_CONVERSATION_FILTERS: ConversationFilters = {
  search: "",
  status: "ALL",
  employeeId: "ALL",
  tag: "ALL",
  unreadOnly: false,
  pinnedOnly: false,
};

interface ConversationUiState {
  selectedConversationId: string | null;
  selectedMessageId: string | null;
  filters: ConversationFilters;
  sort: ConversationSort;
  contextPanelOpen: boolean;
  contextPanelTab: ContextPanelTab;
  /**
   * The assistant message currently playing its streaming reveal. Visual state
   * only — the message is already whole in the cache.
   */
  streamingMessageId: string | null;

  selectConversation: (id: string | null) => void;
  selectMessage: (id: string | null) => void;
  setSearch: (search: string) => void;
  setStatusFilter: (status: ConversationFilters["status"]) => void;
  setEmployeeFilter: (employeeId: ConversationFilters["employeeId"]) => void;
  setTagFilter: (tag: ConversationFilters["tag"]) => void;
  setUnreadOnly: (value: boolean) => void;
  setPinnedOnly: (value: boolean) => void;
  resetFilters: () => void;
  setSort: (sort: ConversationSort) => void;
  setContextPanelOpen: (open: boolean) => void;
  setContextPanelTab: (tab: ContextPanelTab) => void;
  setStreamingMessageId: (id: string | null) => void;
}

export const useConversationStore = create<ConversationUiState>()(
  persist(
    (set) => ({
      selectedConversationId: null,
      selectedMessageId: null,
      filters: EMPTY_CONVERSATION_FILTERS,
      sort: "recent",
      contextPanelOpen: true,
      contextPanelTab: "context",
      streamingMessageId: null,

      // A new conversation is a new context: the message selection and any
      // playing reveal belong to the thread being left behind.
      selectConversation: (id) =>
        set({ selectedConversationId: id, selectedMessageId: null, streamingMessageId: null }),
      selectMessage: (id) => set({ selectedMessageId: id }),
      setSearch: (search) => set((s) => ({ filters: { ...s.filters, search } })),
      setStatusFilter: (status) => set((s) => ({ filters: { ...s.filters, status } })),
      setEmployeeFilter: (employeeId) => set((s) => ({ filters: { ...s.filters, employeeId } })),
      setTagFilter: (tag) => set((s) => ({ filters: { ...s.filters, tag } })),
      setUnreadOnly: (unreadOnly) => set((s) => ({ filters: { ...s.filters, unreadOnly } })),
      setPinnedOnly: (pinnedOnly) => set((s) => ({ filters: { ...s.filters, pinnedOnly } })),
      resetFilters: () => set({ filters: EMPTY_CONVERSATION_FILTERS }),
      setSort: (sort) => set({ sort }),
      setContextPanelOpen: (contextPanelOpen) => set({ contextPanelOpen }),
      setContextPanelTab: (contextPanelTab) => set({ contextPanelTab }),
      setStreamingMessageId: (streamingMessageId) => set({ streamingMessageId }),
    }),
    { name: "neuraevo.conversations", partialize: (s) => ({ contextPanelOpen: s.contextPanelOpen }) }
  )
);

/** True when any facet is narrowing the list — drives the "clear" affordance. */
export const hasActiveConversationFilters = (filters: ConversationFilters): boolean =>
  filters.search.trim() !== "" ||
  filters.status !== "ALL" ||
  filters.employeeId !== "ALL" ||
  filters.tag !== "ALL" ||
  filters.unreadOnly ||
  filters.pinnedOnly;
