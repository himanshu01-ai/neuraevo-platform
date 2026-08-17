"use client";

import { History } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { TONE_DOT } from "@/components/ui/status-badge";
import { useEmployeeActivity } from "../hooks/use-employees";
import { ACTIVITY_META } from "../models/activity-kinds";
import { cn } from "@/lib/utils";

export interface ActivityTimelineProps {
  employeeId: string;
  /** Caps the list where space is tight (the dock); omit to show everything. */
  limit?: number;
  className?: string;
}

/**
 * What has happened to this employee, newest first.
 *
 * Events are ordered, not timed: the platform reports a sequence, so the
 * timeline shows order and refuses to invent clock times it doesn't have. The
 * connector line is drawn once behind the list rather than per item, so it can't
 * drift out of alignment with the markers.
 */
export function ActivityTimeline({ employeeId, limit, className }: ActivityTimelineProps) {
  const query = useEmployeeActivity(employeeId);

  if (query.isPending) return <LoadingState rows={4} className={className} />;

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load activity"
        description="This employee's history couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  const events = limit ? query.data.slice(0, limit) : query.data;

  if (events.length === 0) {
    return (
      <EmptyState
        compact
        icon={History}
        title="No activity yet"
        description="What this employee does will be recorded here."
        className={className}
      />
    );
  }

  return (
    <ol className={cn("relative space-y-4", className)}>
      {/* One continuous rule behind the markers; hidden from the reading order. */}
      <span aria-hidden="true" className="absolute bottom-4 left-[15px] top-4 w-px bg-border" />

      {events.map((event) => {
        const meta = ACTIVITY_META[event.kind];
        const Icon = meta.icon;
        return (
          <li key={event.id} className="relative flex items-start gap-3">
            <span
              className={cn(
                "relative z-10 inline-flex size-8 shrink-0 items-center justify-center rounded-full border bg-card",
                "text-muted-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              <span
                aria-hidden="true"
                className={cn("absolute -bottom-0.5 -right-0.5 size-2 rounded-full ring-2 ring-card", TONE_DOT[meta.tone])}
              />
            </span>
            <span className="min-w-0 flex-1 pt-1">
              <span className="block text-sm text-foreground">{event.summary}</span>
              <span className="block text-xs text-muted-foreground">{meta.label}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
