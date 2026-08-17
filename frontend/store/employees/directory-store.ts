import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { EmployeeCapability, EmployeeRole, EmployeeStatus } from "@/services/employees";

/**
 * The employee directory's client state: which employee is selected, how the
 * list is filtered, and how it's laid out.
 *
 * No server data lives here (docs/09) — the roster stays in the Query cache and
 * this store holds only the questions the user is asking of it. `viewMode` is
 * the one durable preference, so it persists the way `sidebarCollapsed` does;
 * a filter or a selection is a moment, not a setting, and resets on reload.
 */

export type EmployeeViewMode = "grid" | "list";

/** Which section the dock below the split is showing. */
export type EmployeeDockTab = "activity" | "assignments" | "capabilities";

/** `"ALL"` is the unset state for each facet — never a real employee value. */
export interface EmployeeFilters {
  search: string;
  status: EmployeeStatus | "ALL";
  role: EmployeeRole | "ALL";
  capability: EmployeeCapability | "ALL";
}

export const EMPTY_FILTERS: EmployeeFilters = {
  search: "",
  status: "ALL",
  role: "ALL",
  capability: "ALL",
};

interface DirectoryState {
  selectedEmployeeId: string | null;
  filters: EmployeeFilters;
  viewMode: EmployeeViewMode;
  dockTab: EmployeeDockTab;

  selectEmployee: (id: string | null) => void;
  setSearch: (search: string) => void;
  setStatusFilter: (status: EmployeeFilters["status"]) => void;
  setRoleFilter: (role: EmployeeFilters["role"]) => void;
  setCapabilityFilter: (capability: EmployeeFilters["capability"]) => void;
  resetFilters: () => void;
  setViewMode: (mode: EmployeeViewMode) => void;
  setDockTab: (tab: EmployeeDockTab) => void;
}

export const useDirectoryStore = create<DirectoryState>()(
  persist(
    (set) => ({
      selectedEmployeeId: null,
      filters: EMPTY_FILTERS,
      viewMode: "grid",
      dockTab: "activity",

      selectEmployee: (id) => set({ selectedEmployeeId: id }),
      setSearch: (search) => set((s) => ({ filters: { ...s.filters, search } })),
      setStatusFilter: (status) => set((s) => ({ filters: { ...s.filters, status } })),
      setRoleFilter: (role) => set((s) => ({ filters: { ...s.filters, role } })),
      setCapabilityFilter: (capability) => set((s) => ({ filters: { ...s.filters, capability } })),
      resetFilters: () => set({ filters: EMPTY_FILTERS }),
      setViewMode: (viewMode) => set({ viewMode }),
      setDockTab: (dockTab) => set({ dockTab }),
    }),
    { name: "neuraevo.employees", partialize: (s) => ({ viewMode: s.viewMode }) }
  )
);

/** True when any facet is narrowing the list — drives the "clear filters" affordance. */
export const hasActiveFilters = (filters: EmployeeFilters): boolean =>
  filters.search.trim() !== "" ||
  filters.status !== "ALL" ||
  filters.role !== "ALL" ||
  filters.capability !== "ALL";
