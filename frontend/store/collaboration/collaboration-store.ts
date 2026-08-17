import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { EntityKind, NotificationFilters, NotificationType } from "@/services/collaboration";
import { EMPTY_NOTIFICATION_FILTERS } from "@/services/collaboration";
import type { Priority } from "@/types/domain";

/**
 * The collaboration workspace's client state: which notification is selected,
 * how the feed is filtered, and how it's laid out.
 *
 * No server data lives here (docs/09) — the feeds stay in the Query cache and
 * this store holds only the questions the user is asking of them. `viewMode` is
 * the one durable preference, so it persists the way `sidebarCollapsed` does; a
 * filter or a selection is a moment, not a setting, and resets on reload.
 */

/** How the feed rows are laid out. `comfortable` shows descriptions; `compact` hides them. */
export type NotificationViewMode = "comfortable" | "compact";

/** Which section the inspector is showing. */
export type InspectorTab = "details" | "related" | "history";

interface CollaborationState {
  selectedNotificationId: string | null;
  filters: NotificationFilters;
  viewMode: NotificationViewMode;
  inspectorTab: InspectorTab;

  selectNotification: (id: string | null) => void;
  setSearch: (search: string) => void;
  setUnreadOnly: (value: boolean) => void;
  setTypeFilter: (type: NotificationType | "ALL") => void;
  setPriorityFilter: (priority: Priority | "ALL") => void;
  setSourceFilter: (source: EntityKind | "ALL") => void;
  setFromDate: (day: string) => void;
  setToDate: (day: string) => void;
  resetFilters: () => void;
  setViewMode: (mode: NotificationViewMode) => void;
  setInspectorTab: (tab: InspectorTab) => void;
}

export const useCollaborationStore = create<CollaborationState>()(
  persist(
    (set) => ({
      selectedNotificationId: null,
      filters: EMPTY_NOTIFICATION_FILTERS,
      viewMode: "comfortable",
      inspectorTab: "details",

      selectNotification: (id) => set({ selectedNotificationId: id }),
      setSearch: (search) => set((s) => ({ filters: { ...s.filters, search } })),
      setUnreadOnly: (unreadOnly) => set((s) => ({ filters: { ...s.filters, unreadOnly } })),
      setTypeFilter: (type) => set((s) => ({ filters: { ...s.filters, type } })),
      setPriorityFilter: (priority) => set((s) => ({ filters: { ...s.filters, priority } })),
      setSourceFilter: (source) => set((s) => ({ filters: { ...s.filters, source } })),
      setFromDate: (fromDate) => set((s) => ({ filters: { ...s.filters, fromDate } })),
      setToDate: (toDate) => set((s) => ({ filters: { ...s.filters, toDate } })),
      resetFilters: () => set({ filters: EMPTY_NOTIFICATION_FILTERS }),
      setViewMode: (viewMode) => set({ viewMode }),
      setInspectorTab: (inspectorTab) => set({ inspectorTab }),
    }),
    { name: "neuraevo.collaboration", partialize: (s) => ({ viewMode: s.viewMode }) }
  )
);

/** True when any facet is narrowing the feed — drives the "clear" affordance. */
export const hasActiveNotificationFilters = (filters: NotificationFilters): boolean =>
  filters.search.trim() !== "" ||
  filters.unreadOnly ||
  filters.type !== "ALL" ||
  filters.priority !== "ALL" ||
  filters.source !== "ALL" ||
  filters.fromDate !== "" ||
  filters.toDate !== "";
