"use client";

import { memo } from "react";
import { motion } from "framer-motion";
import type { EmployeeSummary } from "@/services/employees";
import { EmployeeAvatar } from "../components/employee-avatar";
import { EmployeeStatusBadge } from "../components/employee-status-badge";
import { roleLabel } from "../models/employee-roles";
import { cn } from "@/lib/utils";

export interface EmployeeListRowProps {
  employee: EmployeeSummary;
  isSelected: boolean;
  onSelect: (id: string) => void;
}

/**
 * One employee, compactly — the directory's dense mode. Says who it is, what it
 * does, and how it's doing; the card says the rest.
 *
 * The selection marker is one shared element (`layoutId`) rather than one per
 * row, so it slides from the old selection to the new instead of blinking.
 * Reduced motion collapses that to a cut via the global MotionConfig.
 */
export const EmployeeListRow = memo(function EmployeeListRow({
  employee,
  isSelected,
  onSelect,
}: EmployeeListRowProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(employee.id)}
      aria-pressed={isSelected}
      className={cn(
        "relative flex w-full items-center gap-3 overflow-hidden rounded-md border px-3 py-2.5 text-left transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isSelected ? "border-primary/40 bg-primary/5" : "border-transparent hover:bg-accent"
      )}
    >
      {isSelected ? (
        <motion.span
          layoutId="employee-selection"
          aria-hidden="true"
          className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary"
          transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        />
      ) : null}

      <EmployeeAvatar name={employee.name} accent={employee.accent} glyph={employee.glyph} size="sm" />

      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{employee.name}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {roleLabel(employee.role, employee.customRole)}
        </span>
      </span>

      <EmployeeStatusBadge status={employee.status} className="shrink-0" />
    </button>
  );
});
