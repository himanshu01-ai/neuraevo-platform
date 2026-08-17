"use client";

import { LayoutGrid, List, Search, X } from "lucide-react";
import {
  EMPLOYEE_CAPABILITIES,
  EMPLOYEE_ROLES,
  EMPLOYEE_STATUS,
  EMPLOYEE_STATUS_LABEL,
  type EmployeeCapability,
  type EmployeeRole,
  type EmployeeStatus,
} from "@/services/employees";
import { hasActiveFilters, useDirectoryStore, type EmployeeViewMode } from "@/store/employees";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { CAPABILITY_META } from "../models/employee-capabilities";
import { ROLE_META } from "../models/employee-roles";
import { cn } from "@/lib/utils";

const VIEW_MODES: { mode: EmployeeViewMode; label: string; icon: typeof LayoutGrid }[] = [
  { mode: "grid", label: "Cards", icon: LayoutGrid },
  { mode: "list", label: "Compact", icon: List },
];

/**
 * How the directory is narrowed and how it's laid out.
 *
 * Every control writes straight to the directory store, and the list derives
 * from it — so the filters never hold a second copy of what's showing.
 */
export function EmployeeFilters({ className }: { className?: string }) {
  const filters = useDirectoryStore((s) => s.filters);
  const viewMode = useDirectoryStore((s) => s.viewMode);
  const setSearch = useDirectoryStore((s) => s.setSearch);
  const setStatusFilter = useDirectoryStore((s) => s.setStatusFilter);
  const setRoleFilter = useDirectoryStore((s) => s.setRoleFilter);
  const setCapabilityFilter = useDirectoryStore((s) => s.setCapabilityFilter);
  const resetFilters = useDirectoryStore((s) => s.resetFilters);
  const setViewMode = useDirectoryStore((s) => s.setViewMode);

  const isFiltered = hasActiveFilters(filters);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          type="search"
          value={filters.search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search employees"
          aria-label="Search employees"
          className="pl-9"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={filters.status}
          onChange={(event) => setStatusFilter(event.target.value as EmployeeStatus | "ALL")}
          aria-label="Filter by status"
          className="h-8 w-auto min-w-32 flex-1 text-xs sm:flex-none"
        >
          <option value="ALL">Any status</option>
          {EMPLOYEE_STATUS.map((status) => (
            <option key={status} value={status}>
              {EMPLOYEE_STATUS_LABEL[status]}
            </option>
          ))}
        </Select>

        <Select
          value={filters.role}
          onChange={(event) => setRoleFilter(event.target.value as EmployeeRole | "ALL")}
          aria-label="Filter by role"
          className="h-8 w-auto min-w-32 flex-1 text-xs sm:flex-none"
        >
          <option value="ALL">Any role</option>
          {EMPLOYEE_ROLES.map((role) => (
            <option key={role} value={role}>
              {ROLE_META[role].label}
            </option>
          ))}
        </Select>

        <Select
          value={filters.capability}
          onChange={(event) => setCapabilityFilter(event.target.value as EmployeeCapability | "ALL")}
          aria-label="Filter by capability"
          className="h-8 w-auto min-w-32 flex-1 text-xs sm:flex-none"
        >
          <option value="ALL">Any capability</option>
          {EMPLOYEE_CAPABILITIES.map((capability) => (
            <option key={capability} value={capability}>
              {CAPABILITY_META[capability].label}
            </option>
          ))}
        </Select>

        {isFiltered ? (
          <Button variant="ghost" size="sm" className="h-8" onClick={resetFilters}>
            <X className="size-4" aria-hidden="true" />
            Clear
          </Button>
        ) : null}

        {/* Segmented control: one group, one pressed button. */}
        <div
          role="group"
          aria-label="View mode"
          className="ml-auto flex shrink-0 items-center gap-0.5 rounded-md border bg-background p-0.5"
        >
          {VIEW_MODES.map(({ mode, label, icon: Icon }) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              aria-pressed={viewMode === mode}
              className={cn(
                "inline-flex size-7 items-center justify-center rounded-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                viewMode === mode
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              <span className="sr-only">{label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
