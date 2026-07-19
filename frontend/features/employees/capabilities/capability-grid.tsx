"use client";

import { useMemo } from "react";
import { ErrorState } from "@/components/ui/error-state";
import { Shimmer } from "@/components/ui/shimmer";
import { useEmployeeCapabilities } from "../hooks/use-employees";
import { CapabilityCard } from "./capability-card";
import { cn } from "@/lib/utils";

export interface CapabilityGridProps {
  employeeId: string;
  className?: string;
}

/**
 * Every capability the platform offers, marked with whether this employee holds
 * it — granted first, so what the employee *can* do reads before what it can't.
 *
 * Configuration is described, not offered: none of these do anything until the
 * platform can run them (Sprint 17.7 and beyond).
 */
export function CapabilityGrid({ employeeId, className }: CapabilityGridProps) {
  const query = useEmployeeCapabilities(employeeId);

  const ordered = useMemo(() => {
    const states = query.data ?? [];
    // Stable: granted before ungranted, canonical order preserved within each.
    return [
      ...states.filter((s) => s.status === "GRANTED"),
      ...states.filter((s) => s.status !== "GRANTED"),
    ];
  }, [query.data]);

  if (query.isPending) {
    return (
      <div
        role="status"
        aria-label="Loading capabilities"
        className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-3", className)}
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <Shimmer key={i} className="h-48" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load capabilities"
        description="This employee's capabilities couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-3", className)}>
      {ordered.map((state) => (
        <CapabilityCard key={state.capability} state={state} />
      ))}
    </div>
  );
}
