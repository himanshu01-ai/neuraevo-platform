"use client";

import { memo, useEffect, useRef, useState } from "react";
import { Archive, Copy, Ellipsis, Pencil, Trash2 } from "lucide-react";
import type { EmployeeSummary } from "@/services/employees";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { StatusBadge } from "@/components/ui/status-badge";
import { CapabilityChips } from "../components/capability-chips";
import { EmployeeAvatar } from "../components/employee-avatar";
import { EmployeeStatusBadge } from "../components/employee-status-badge";
import { roleLabel } from "../models/employee-roles";
import { cn } from "@/lib/utils";

export interface EmployeeCardProps {
  employee: EmployeeSummary;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
  /** The employee, not its id — the directory names it in the confirmation. */
  onDuplicate: (employee: EmployeeSummary) => void;
  onArchive: (employee: EmployeeSummary) => void;
  onDelete: (employee: EmployeeSummary) => void;
}

/**
 * One employee at a glance: who it is, what it can do, how it's doing, and what
 * it's on. Everything the directory promises about an employee is here, so a
 * card and a profile never tell different stories.
 *
 * The card body is a button, not a link: selecting an employee fills the details
 * panel beside it rather than navigating. The actions menu sits outside that
 * button so its clicks aren't swallowed.
 *
 * Delete asks first, inline. Removing someone's work on a single click of a menu
 * item is not a thing to do, and the confirmation lives here so the list doesn't
 * have to track which card is asking.
 */
export const EmployeeCard = memo(function EmployeeCard({
  employee,
  isSelected = false,
  onSelect,
  onDuplicate,
  onArchive,
  onDelete,
}: EmployeeCardProps) {
  const [isConfirming, setIsConfirming] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const role = roleLabel(employee.role, employee.customRole);

  // Choosing Delete closes the menu, which leaves focus nowhere. Move it to the
  // confirmation — on Cancel, the safe half, so a stray Enter dismisses rather
  // than deletes.
  useEffect(() => {
    if (isConfirming) cancelRef.current?.focus();
  }, [isConfirming]);

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-lg border bg-card p-4 shadow-sm transition-all",
        "hover:border-primary/30 hover:shadow-md",
        isSelected && "border-primary/50 ring-2 ring-primary/30"
      )}
    >
      <div className="flex items-start gap-3">
        <EmployeeAvatar name={employee.name} accent={employee.accent} glyph={employee.glyph} size="md" />

        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-foreground">
            {onSelect ? (
              // Stretched over the card so the whole surface selects, while the
              // menu and the confirm buttons stay clickable above it.
              <button
                type="button"
                onClick={() => onSelect(employee.id)}
                aria-pressed={isSelected}
                className="rounded-sm text-left after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {employee.name}
              </button>
            ) : (
              employee.name
            )}
          </h3>
          <p className="truncate text-xs text-muted-foreground">{role}</p>
        </div>

        <div className="relative z-10 flex shrink-0 items-center gap-1.5">
          <EmployeeStatusBadge status={employee.status} />
          <DropdownMenu
            menuLabel={`Actions for ${employee.name}`}
            align="end"
            items={[
              {
                key: "edit",
                label: "Edit employee",
                icon: Pencil,
                href: `/workspace/employees/${employee.id}/edit`,
              },
              { key: "duplicate", label: "Duplicate", icon: Copy, onSelect: () => onDuplicate(employee) },
              {
                key: "archive",
                label: "Archive",
                icon: Archive,
                onSelect: () => onArchive(employee),
              },
              {
                key: "delete",
                label: "Delete",
                icon: Trash2,
                destructive: true,
                onSelect: () => setIsConfirming(true),
              },
            ]}
            renderTrigger={(props) => (
              <Button
                {...props}
                variant="ghost"
                size="icon"
                className="size-7 text-muted-foreground"
                aria-label={`Actions for ${employee.name}`}
              >
                <Ellipsis className="size-4" aria-hidden="true" />
              </Button>
            )}
          />
        </div>
      </div>

      <p className="mt-3 line-clamp-2 flex-1 text-sm text-muted-foreground">{employee.description}</p>

      <CapabilityChips capabilities={employee.capabilities} className="mt-3" />

      {isConfirming ? (
        <div
          role="alert"
          className="relative z-10 mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-2.5"
        >
          <p className="text-xs text-destructive">Delete “{employee.name}”? This can&apos;t be undone.</p>
          <div className="mt-2 flex gap-2">
            <Button
              variant="destructive"
              size="sm"
              className="h-7 flex-1"
              onClick={() => {
                setIsConfirming(false);
                onDelete(employee);
              }}
            >
              Delete
            </Button>
            <Button
              ref={cancelRef}
              variant="outline"
              size="sm"
              className="h-7 flex-1"
              onClick={() => setIsConfirming(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 space-y-2 border-t pt-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-muted-foreground">
              {employee.assignedWorkflows} workflow{employee.assignedWorkflows === 1 ? "" : "s"}
            </span>
            <StatusBadge kind="health" status={employee.health} />
          </div>
          <p className="truncate text-xs text-muted-foreground">
            <span className="sr-only">Last activity: </span>
            {employee.lastActivity}
          </p>
        </div>
      )}
    </div>
  );
});
