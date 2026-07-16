import { Brain } from "lucide-react";
import type { EmployeeMemorySummary } from "@/services/employees";
import { EmptyState } from "@/components/ui/empty-state";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export interface ProfileMemoryProps {
  memory: EmployeeMemorySummary;
  className?: string;
}

/**
 * What this employee has learned, as counts the Memory Engine already reports
 * (Sprint 2E). The bars show each category's share of the total — a proportion
 * of numbers the platform gave us, not a new measurement.
 */
export function ProfileMemory({ memory, className }: ProfileMemoryProps) {
  if (memory.total === 0) {
    return (
      <EmptyState
        compact
        icon={Brain}
        title="Nothing remembered yet"
        description="What this employee learns will show up here."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums text-foreground">{memory.total}</span>
        <span className="text-sm text-muted-foreground">
          {memory.total === 1 ? "memory" : "memories"} stored
        </span>
      </div>

      <ul className="space-y-2.5">
        {memory.categories.map((entry) => {
          const share = Math.round((entry.count / memory.total) * 100);
          return (
            <li key={entry.category}>
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate text-foreground">{entry.category}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">{entry.count}</span>
              </div>
              <Progress value={share} label={`${entry.category}: ${share}% of memories`} className="mt-1.5" />
            </li>
          );
        })}
      </ul>

      {memory.latest ? (
        <div className="rounded-md border bg-background p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Most recent
          </h4>
          <p className="mt-1 text-sm text-foreground">{memory.latest}</p>
        </div>
      ) : null}
    </div>
  );
}
