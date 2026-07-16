"use client";

import { useCallback } from "react";
import { motion } from "framer-motion";
import type { EmployeeSummary } from "@/services/employees";
import { useDirectoryStore, type EmployeeViewMode } from "@/store/employees";
import { EmployeeCard } from "../cards/employee-card";
import { EmployeeListRow } from "../cards/employee-list-row";
import {
  useArchiveEmployee,
  useDeleteEmployee,
  useDuplicateEmployee,
} from "../hooks/use-employees";
import { cn } from "@/lib/utils";

export interface EmployeeListProps {
  employees: readonly EmployeeSummary[];
  viewMode: EmployeeViewMode;
  className?: string;
}

/**
 * The directory's roster column.
 *
 * Both modes render the same employees, differing only in how much they say:
 * cards are roomy, rows are dense. Handlers are `useCallback`-stable and the
 * items are memoized, so filtering or selecting re-renders the one item that
 * changed rather than the whole list.
 *
 * Rows animate in but not out. <AnimatePresence> would be the usual way to get
 * an exit, but framer-motion 11 and React 19 disagree about it badly enough that
 * filtered-out rows stay mounted — a wrong list is a worse outcome than a missing
 * flourish, so the exit goes. The workflow list (Sprint 17.5) renders without one
 * for the same reason.
 */
export function EmployeeList({ employees, viewMode, className }: EmployeeListProps) {
  const selectedEmployeeId = useDirectoryStore((s) => s.selectedEmployeeId);
  const selectEmployee = useDirectoryStore((s) => s.selectEmployee);

  const duplicate = useDuplicateEmployee();
  const archive = useArchiveEmployee();
  const remove = useDeleteEmployee();

  const handleSelect = useCallback((id: string) => selectEmployee(id), [selectEmployee]);
  const handleDuplicate = useCallback((id: string) => duplicate.mutate(id), [duplicate]);
  const handleArchive = useCallback((id: string) => archive.mutate(id), [archive]);

  const handleDelete = useCallback(
    (id: string) => {
      remove.mutate(id);
      // Deleting the selected employee would leave the details panel pointing at
      // nothing; clear the selection with it.
      if (selectedEmployeeId === id) selectEmployee(null);
    },
    [remove, selectedEmployeeId, selectEmployee]
  );

  return (
    <ul className={cn(viewMode === "grid" ? "space-y-3" : "space-y-1", className)}>
      {employees.map((employee) => (
        <motion.li
          key={employee.id}
          layout="position"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          {viewMode === "grid" ? (
            <EmployeeCard
              employee={employee}
              isSelected={selectedEmployeeId === employee.id}
              onSelect={handleSelect}
              onDuplicate={handleDuplicate}
              onArchive={handleArchive}
              onDelete={handleDelete}
            />
          ) : (
            <EmployeeListRow
              employee={employee}
              isSelected={selectedEmployeeId === employee.id}
              onSelect={handleSelect}
            />
          )}
        </motion.li>
      ))}
    </ul>
  );
}
