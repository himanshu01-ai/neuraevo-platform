import { memo } from "react";
import { Lock } from "lucide-react";
import type { EmployeeCapabilityState } from "@/services/employees";
import { Badge } from "@/components/ui/badge";
import { AVAILABILITY_LABEL, CAPABILITY_META } from "../models/employee-capabilities";
import { cn } from "@/lib/utils";

export interface CapabilityCardProps {
  state: EmployeeCapabilityState;
  className?: string;
}

/**
 * One capability as it stands for one employee: what it does, whether this
 * employee holds it, whether the platform offers it yet, and what you'll be able
 * to configure once it runs.
 *
 * A capability the employee doesn't hold is dimmed rather than hidden — knowing
 * what's available but ungranted is the point of the screen. Grant state is said
 * in words, never by opacity alone.
 */
export const CapabilityCard = memo(function CapabilityCard({ state, className }: CapabilityCardProps) {
  const meta = CAPABILITY_META[state.capability];
  const Icon = meta.icon;
  const isGranted = state.status === "GRANTED";

  return (
    <div
      className={cn(
        "flex flex-col rounded-lg border bg-card p-4 shadow-sm transition-colors",
        !isGranted && "border-dashed",
        className
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span
          className={cn(
            "inline-flex size-9 shrink-0 items-center justify-center rounded-md",
            isGranted ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="size-5" aria-hidden="true" />
        </span>

        {isGranted ? (
          <Badge variant="success">
            <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-success" />
            Granted
          </Badge>
        ) : (
          <Badge variant="default">
            <Lock className="size-3 shrink-0" aria-hidden="true" />
            Not granted
          </Badge>
        )}
      </div>

      <h4 className={cn("mt-3 text-sm font-semibold", isGranted ? "text-foreground" : "text-muted-foreground")}>
        {meta.label}
      </h4>
      <p className="mt-1 flex-1 text-sm text-muted-foreground">{meta.description}</p>

      <dl className="mt-3 space-y-2 border-t pt-3 text-xs">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Availability</dt>
          <dd>
            {/* Availability is a fact about the platform, not a status of the
                employee — so it stays outline, off the status palette. */}
            <Badge variant="outline">{AVAILABILITY_LABEL[state.availability]}</Badge>
          </dd>
        </div>
        <div className="space-y-1">
          <dt className="text-muted-foreground">Configuration</dt>
          <dd className="text-muted-foreground">{meta.futureConfiguration}</dd>
        </div>
      </dl>
    </div>
  );
});
