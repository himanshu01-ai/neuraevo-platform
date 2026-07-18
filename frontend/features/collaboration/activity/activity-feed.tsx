"use client";

import { memo } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Activity as ActivityIcon } from "lucide-react";
import type { ActivityEvent } from "@/services/collaboration";
import { ACTIVITY_KIND_LABEL, ACTIVITY_KIND_TONE } from "@/services/collaboration";
import { Avatar } from "@/components/ui/avatar";
import { EmptyState } from "@/components/ui/empty-state";
import { TONE_DOT } from "@/components/ui/status-badge";
import { formatDayTime } from "@/utils/format";
import { ACTIVITY_KIND_ICON } from "../models/notification-meta";
import { EntityChip } from "../references/entity-reference-card";
import { cn } from "@/lib/utils";

/**
 * A single activity event: who did what, to which record, and when. The actor's
 * avatar anchors the row; the kind's icon and tone mark the verb. Memoized —
 * feeds re-render on filter changes and settled rows don't change.
 */
const ActivityRow = memo(function ActivityRow({ event }: { event: ActivityEvent }) {
  const Icon = ACTIVITY_KIND_ICON[event.kind];
  const tone = ACTIVITY_KIND_TONE[event.kind];

  return (
    <div className="flex gap-3 rounded-lg border bg-card p-3 shadow-sm">
      <div className="relative shrink-0">
        <Avatar name={event.actor.name} />
        <span
          className={cn(
            "absolute -bottom-1 -right-1 inline-flex size-4 items-center justify-center rounded-full border-2 border-card",
            TONE_DOT[tone]
          )}
          aria-hidden="true"
        >
          <Icon className="size-2.5 text-background" />
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-foreground">{event.summary}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{ACTIVITY_KIND_LABEL[event.kind]}</span>
          <span aria-hidden="true">·</span>
          <time dateTime={event.createdAt}>{formatDayTime(event.createdAt)}</time>
          {event.entity ? <EntityChip entity={event.entity} className="ml-1" /> : null}
        </div>
      </div>
    </div>
  );
});

export interface ActivityFeedProps {
  events: ActivityEvent[];
  emptyTitle?: string;
  emptyDescription?: string;
  className?: string;
}

/** A timeline of activity events with a staggered reveal, reduced-motion aware. */
export function ActivityFeed({
  events,
  emptyTitle = "No activity yet",
  emptyDescription = "Activity from you and your AI employees will appear here.",
  className,
}: ActivityFeedProps) {
  const reducedMotion = useReducedMotion();

  if (events.length === 0) {
    return <EmptyState icon={ActivityIcon} title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <ul className={cn("flex flex-col gap-2", className)} aria-label="Activity feed">
      {events.map((event, index) => (
        <motion.li
          key={event.id}
          initial={{ opacity: 0, y: reducedMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: reducedMotion ? 0 : Math.min(index * 0.03, 0.3), ease: [0.16, 1, 0.3, 1] }}
        >
          <ActivityRow event={event} />
        </motion.li>
      ))}
    </ul>
  );
}
