"use client";

import { useMemo } from "react";
import type { EmployeeSummary } from "@/services/employees";
import type { EmployeeFilters } from "@/store/employees";
import { roleLabel } from "../models/employee-roles";

/**
 * The roster narrowed by the directory's filters.
 *
 * Filtering is derived, never stored: the store holds the question, the Query
 * cache holds the roster, and this recomputes the answer. Nothing to keep in
 * sync, so nothing can drift.
 *
 * Search matches the name, the description, and the role *as it reads on screen*
 * — someone searching "research" means the words they can see, not the
 * `RESEARCH_ASSISTANT` token underneath.
 */
export function useFilteredEmployees(
  employees: readonly EmployeeSummary[] | undefined,
  filters: EmployeeFilters
): EmployeeSummary[] {
  return useMemo(() => {
    const rows = employees ?? [];
    const term = filters.search.trim().toLowerCase();

    return rows.filter((employee) => {
      if (filters.status !== "ALL" && employee.status !== filters.status) return false;
      if (filters.role !== "ALL" && employee.role !== filters.role) return false;
      if (filters.capability !== "ALL" && !employee.capabilities.includes(filters.capability)) return false;
      if (!term) return true;

      const haystack = [
        employee.name,
        employee.description,
        roleLabel(employee.role, employee.customRole),
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(term);
    });
  }, [employees, filters]);
}
