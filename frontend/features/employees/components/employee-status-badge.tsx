import { Badge } from "@/components/ui/badge";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { EMPLOYEE_STATUS_LABEL, EMPLOYEE_STATUS_TONE, type EmployeeStatus } from "@/services/employees";
import { cn } from "@/lib/utils";

export interface EmployeeStatusBadgeProps {
  status: EmployeeStatus;
  className?: string;
}

/**
 * An employee's status as a dot plus a label, so status is never carried by
 * colour alone. WORKING breathes the way RUNNING does elsewhere; the global
 * reduced-motion rule stills it.
 *
 * This composes <Badge> with the tone tables `StatusBadge` exports rather than
 * extending `StatusBadge` itself: that primitive resolves the vocabularies in
 * `types/domain.ts`, which mirror the frozen backend, and employee status has no
 * backend counterpart to mirror (see `services/employees/types.ts`). Same
 * primitive, same tones, same pixels — one vocabulary short of belonging there.
 */
export function EmployeeStatusBadge({ status, className }: EmployeeStatusBadgeProps) {
  const tone = EMPLOYEE_STATUS_TONE[status];

  return (
    <Badge variant={TONE_VARIANT[tone]} className={className}>
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          TONE_DOT[tone],
          status === "WORKING" && "animate-pulse-glow"
        )}
      />
      {EMPLOYEE_STATUS_LABEL[status]}
    </Badge>
  );
}
