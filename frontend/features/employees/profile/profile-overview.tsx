import type { EmployeeDetail } from "@/services/employees";
import { StatusBadge } from "@/components/ui/status-badge";
import { CapabilityChips } from "../components/capability-chips";
import { EmployeeAvatar } from "../components/employee-avatar";
import { EmployeeStatusBadge } from "../components/employee-status-badge";
import { roleLabel } from "../models/employee-roles";
import { cn } from "@/lib/utils";

export interface ProfileOverviewProps {
  employee: EmployeeDetail;
  className?: string;
}

/** Who this employee is, in its own words, plus the numbers that describe it. */
export function ProfileOverview({ employee, className }: ProfileOverviewProps) {
  const facts: { label: string; value: string }[] = [
    {
      label: "Workflows",
      value: `${employee.assignedWorkflows}`,
    },
    {
      label: "Capabilities",
      value: `${employee.capabilities.length}`,
    },
    {
      label: "Memories",
      value: `${employee.memory.total}`,
    },
    {
      label: "In queue",
      value: `${employee.assignments.queue.length}`,
    },
  ];

  return (
    <div className={cn("space-y-5", className)}>
      <div className="flex items-start gap-4">
        <EmployeeAvatar name={employee.name} accent={employee.accent} glyph={employee.glyph} size="lg" />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-md font-semibold text-foreground">{employee.name}</h3>
          <p className="truncate text-sm text-muted-foreground">
            {roleLabel(employee.role, employee.customRole)}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <EmployeeStatusBadge status={employee.status} />
            <StatusBadge kind="health" status={employee.health} />
          </div>
        </div>
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">{employee.description}</p>

      {employee.behaviorSummary ? (
        <div className="rounded-md border-l-2 border-primary/40 bg-muted/40 py-2 pl-3 pr-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            How it works
          </h4>
          <p className="mt-1 text-sm leading-relaxed text-foreground">{employee.behaviorSummary}</p>
        </div>
      ) : null}

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Capabilities</h4>
        <CapabilityChips capabilities={employee.capabilities} max={9} className="mt-2" />
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {facts.map((fact) => (
          <div key={fact.label} className="rounded-md border bg-background p-3">
            <dt className="text-xs text-muted-foreground">{fact.label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">{fact.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
