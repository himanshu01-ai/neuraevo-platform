"use client";

import { motion } from "framer-motion";
import type { EmployeeSummary } from "@/services/employees";
import { useDirectoryStore, type EmployeeViewMode } from "@/store/employees";
import { EmployeeCard } from "../cards/employee-card";
import { EmployeeListRow } from "../cards/employee-list-row";
import { cn } from "@/lib/utils";

export interface EmployeeListProps {
  employees: readonly EmployeeSummary[];
  viewMode: EmployeeViewMode;
  /**
   * The roster renders the actions but doesn't perform them: the directory owns
   * the mutations, so their result has somewhere to be reported even when the
   * list this was triggered from is no longer on screen.
   */
  onDuplicate: (employee: EmployeeSummary) => void;
  onArchive: (employee: EmployeeSummary) => void;
  onRestore: (employee: EmployeeSummary) => void;
  onDelete: (employee: EmployeeSummary) => void;
  className?: string;
}

/**
 * The directory's roster column.
 *
 * Both modes render the same employees, differing only in how much they say:
 * cards are roomy, rows are dense. The handlers arrive already stable from
 * `useEmployeeActions` and the items are memoized, so filtering or selecting
 * re-renders the one item that changed rather than the whole list.
 *
 * Rows animate in but not out. <AnimatePresence> would be the usual way to get
 * an exit, but framer-motion 11 and React 19 disagree about it badly enough that
 * filtered-out rows stay mounted — a wrong list is a worse outcome than a missing
 * flourish, so the exit goes. The workflow list (Sprint 17.5) renders without one
 * for the same reason.
 */
export function EmployeeList({
  employees,
  viewMode,
  onDuplicate,
  onArchive,
  onRestore,
  onDelete,
  className,
}: EmployeeListProps) {
  const selectedEmployeeId = useDirectoryStore((s) => s.selectedEmployeeId);
  const selectEmployee = useDirectoryStore((s) => s.selectEmployee);

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
              onSelect={selectEmployee}
              onDuplicate={onDuplicate}
              onArchive={onArchive}
              onRestore={onRestore}
              onDelete={onDelete}
            />
          ) : (
            <EmployeeListRow
              employee={employee}
              isSelected={selectedEmployeeId === employee.id}
              onSelect={selectEmployee}
            />
          )}
        </motion.li>
      ))}
    </ul>
  );
}
