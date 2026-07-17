import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Priority } from "@/types/domain";
import type { TaskExecutionMode, TaskState } from "@/services/tasks";

/**
 * The task directory's client state: which task is selected, how the board is
 * filtered and sorted, and how it's laid out.
 *
 * No server data lives here (docs/09) — the board stays in the Query cache and
 * this store holds only the questions the user is asking of it. `viewMode` is
 * the one durable preference, so it persists the way `sidebarCollapsed` does; a
 * filter or a selection is a moment, not a setting, and resets on reload.
 */

export type TaskViewMode = "grid" | "list";

/** Which section the dock below the split is showing. */
export type TaskDockTab = "timeline" | "artifacts" | "approvals" | "results";

/** How the board is ordered. `recent` is the platform's own sequence. */
export const TASK_SORTS = ["recent", "priority", "state", "progress"] as const;
export type TaskSort = (typeof TASK_SORTS)[number];

export const TASK_SORT_LABEL: Record<TaskSort, string> = {
  recent: "Most recent",
  priority: "Priority",
  state: "State",
  progress: "Progress",
};

/** `"ALL"` is the unset state for each facet — never a real task value. */
export interface TaskFilters {
  search: string;
  state: TaskState | "ALL";
  priority: Priority | "ALL";
  executionMode: TaskExecutionMode | "ALL";
}

export const EMPTY_TASK_FILTERS: TaskFilters = {
  search: "",
  state: "ALL",
  priority: "ALL",
  executionMode: "ALL",
};

interface TaskState_ {
  selectedTaskId: string | null;
  filters: TaskFilters;
  sort: TaskSort;
  viewMode: TaskViewMode;
  dockTab: TaskDockTab;

  selectTask: (id: string | null) => void;
  setSearch: (search: string) => void;
  setStateFilter: (state: TaskFilters["state"]) => void;
  setPriorityFilter: (priority: TaskFilters["priority"]) => void;
  setExecutionModeFilter: (mode: TaskFilters["executionMode"]) => void;
  resetFilters: () => void;
  setSort: (sort: TaskSort) => void;
  setViewMode: (mode: TaskViewMode) => void;
  setDockTab: (tab: TaskDockTab) => void;
}

export const useTaskStore = create<TaskState_>()(
  persist(
    (set) => ({
      selectedTaskId: null,
      filters: EMPTY_TASK_FILTERS,
      sort: "recent",
      viewMode: "list",
      dockTab: "timeline",

      selectTask: (id) => set({ selectedTaskId: id }),
      setSearch: (search) => set((s) => ({ filters: { ...s.filters, search } })),
      setStateFilter: (state) => set((s) => ({ filters: { ...s.filters, state } })),
      setPriorityFilter: (priority) => set((s) => ({ filters: { ...s.filters, priority } })),
      setExecutionModeFilter: (executionMode) => set((s) => ({ filters: { ...s.filters, executionMode } })),
      resetFilters: () => set({ filters: EMPTY_TASK_FILTERS }),
      setSort: (sort) => set({ sort }),
      setViewMode: (viewMode) => set({ viewMode }),
      setDockTab: (dockTab) => set({ dockTab }),
    }),
    { name: "neuraevo.tasks", partialize: (s) => ({ viewMode: s.viewMode }) }
  )
);

/** True when any facet is narrowing the board — drives the "clear" affordance. */
export const hasActiveTaskFilters = (filters: TaskFilters): boolean =>
  filters.search.trim() !== "" ||
  filters.state !== "ALL" ||
  filters.priority !== "ALL" ||
  filters.executionMode !== "ALL";
