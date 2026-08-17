"use client";

import { useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { History } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { TONE_DOT } from "@/components/ui/status-badge";
import { formatDateTime } from "@/utils/format";
import { useMemoryTimeline } from "../hooks/use-memory";
import { TIMELINE_EVENT_META } from "../models/timeline-events";
import { cn } from "@/lib/utils";

export interface MemoryTimelineProps {
  /** One memory's history, or the whole workspace's when `null`. */
  memoryId: string | null;
  /** Caps the list where space is tight (the dock); omit to show everything. */
  limit?: number;
  /** Link each event to the memory it concerns. Off on a memory's own screen. */
  showMemory?: boolean;
  className?: string;
}

/**
 * What has happened to the knowledge, newest first.
 *
 * These events carry real timestamps rather than the ordinal sequences the rest
 * of this app uses — the Memory Engine stores `created_at` as a real
 * `DateTime(timezone=True)`, so there is an actual time to show and no reason to
 * pretend otherwise. They are formatted through `utils/format`, which pins the
 * locale and the zone to UTC so the day shown is the day the API means.
 *
 * On virtualizing: a workspace's history is bounded by what a query returns, and
 * the fixtures top out at sixteen. Virtualizing tens of rows costs a scroll
 * container and a measurement pass to save nothing — `limit` is the seam if a
 * backend ever returns thousands.
 */
export function MemoryTimeline({ memoryId, limit, showMemory = false, className }: MemoryTimelineProps) {
  const query = useMemoryTimeline(memoryId);

  const events = useMemo(() => {
    const rows = query.data ?? [];
    return limit ? rows.slice(0, limit) : rows;
  }, [query.data, limit]);

  if (query.isPending) return <LoadingState rows={4} className={className} />;

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load the timeline"
        description="This history couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  if (events.length === 0) {
    return (
      <EmptyState
        compact
        icon={History}
        title="Nothing yet"
        description="Changes to this knowledge will show up here."
        className={className}
      />
    );
  }

  return (
    <ol className={cn("relative space-y-3", className)}>
      {/* One continuous rule behind the markers; hidden from the reading order. */}
      <span aria-hidden="true" className="absolute bottom-4 left-[15px] top-4 w-px bg-border" />

      {events.map((event, index) => {
        const meta = TIMELINE_EVENT_META[event.kind];
        const Icon = meta.icon;

        return (
          <motion.li
            key={event.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: Math.min(index * 0.03, 0.24), ease: [0.16, 1, 0.3, 1] }}
            className="relative flex items-start gap-3"
          >
            <span className="relative z-10 inline-flex size-8 shrink-0 items-center justify-center rounded-full border bg-card text-muted-foreground">
              <Icon className="size-4" aria-hidden="true" />
              <span
                aria-hidden="true"
                className={cn(
                  "absolute -bottom-0.5 -right-0.5 size-2 rounded-full ring-2 ring-card",
                  TONE_DOT[meta.tone]
                )}
              />
            </span>

            <span className="min-w-0 flex-1 pt-0.5">
              <span className="block text-sm text-foreground">{event.summary}</span>

              {showMemory && event.memoryId ? (
                <Link
                  href={`/workspace/memory/${event.memoryId}`}
                  className="block truncate rounded-sm text-xs text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {event.memoryTitle}
                </Link>
              ) : null}

              <span className="block text-xs text-muted-foreground">
                {meta.label} · <time dateTime={event.at}>{formatDateTime(event.at)}</time>
              </span>
            </span>
          </motion.li>
        );
      })}
    </ol>
  );
}
