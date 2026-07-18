"use client";

import { memo } from "react";
import { BellOff, Bookmark, Eye, Pin } from "lucide-react";
import type { NotificationSummary } from "@/services/collaboration";
import { NOTIFICATION_TYPE_LABEL, NOTIFICATION_TYPE_TONE } from "@/services/collaboration";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Badge } from "@/components/ui/badge";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { formatDayTime } from "@/utils/format";
import { NOTIFICATION_TYPE_ICON, TONE_SURFACE } from "../models/notification-meta";
import { EntityChip } from "../references/entity-reference-card";
import { QuickActions } from "./quick-actions";
import { cn } from "@/lib/utils";

export interface NotificationCardProps {
  notification: NotificationSummary;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onToggle: (
    id: string,
    field: "read" | "archived" | "pinned" | "bookmarked" | "following" | "muted",
    value: boolean
  ) => void;
  /** `compact` hides the description and entity chip. */
  compact?: boolean;
  disabled?: boolean;
}

/**
 * One notification in the feed: type icon, title, description, source,
 * timestamp, priority, read state, and its quick actions. The row is the select
 * control — picking it fills the inspector beside it rather than navigating. An
 * unread row carries a leading dot and heavier title; status is never carried
 * by colour alone.
 *
 * Memoized: the feed re-renders on filter and selection changes, and a settled
 * row's props don't change.
 */
export const NotificationCard = memo(function NotificationCard({
  notification,
  isSelected,
  onSelect,
  onToggle,
  compact = false,
  disabled = false,
}: NotificationCardProps) {
  const n = notification;
  const Icon = NOTIFICATION_TYPE_ICON[n.type];
  const tone = NOTIFICATION_TYPE_TONE[n.type];

  return (
    <div
      className={cn(
        "relative flex gap-3 rounded-lg border bg-card p-3 shadow-sm transition-all",
        "hover:border-primary/30 hover:shadow-md",
        isSelected && "border-primary/50 ring-2 ring-primary/30",
        !n.read && "border-l-[3px] border-l-primary"
      )}
    >
      <span
        className={cn("mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-md", TONE_SURFACE[tone])}
        aria-hidden="true"
      >
        <Icon className="size-4" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className={cn("min-w-0 text-sm text-foreground", n.read ? "font-medium" : "font-semibold")}>
            <button
              type="button"
              onClick={() => onSelect(n.id)}
              aria-pressed={isSelected}
              className="rounded-sm text-left after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {!n.read ? <span className="sr-only">Unread: </span> : null}
              {n.title}
            </button>
          </h3>
          <div className="relative z-10 flex shrink-0 items-center gap-1">
            <Badge variant={TONE_VARIANT[PRIORITY_TONE[n.priority]]} className="hidden sm:inline-flex">
              {PRIORITY_LABEL[n.priority]}
            </Badge>
            <QuickActions notification={n} onToggle={onToggle} disabled={disabled} />
          </div>
        </div>

        {!compact ? (
          <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{n.description}</p>
        ) : null}

        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span aria-hidden="true" className={cn("size-1.5 rounded-full", TONE_DOT[tone])} />
            {NOTIFICATION_TYPE_LABEL[n.type]}
          </span>
          <span aria-hidden="true">·</span>
          <span className="truncate">{n.source.name}</span>
          <span aria-hidden="true">·</span>
          <time dateTime={n.createdAt}>{formatDayTime(n.createdAt)}</time>

          {!compact && n.primaryEntity ? <EntityChip entity={n.primaryEntity} className="ml-1" /> : null}

          <span className="ml-auto flex items-center gap-1.5">
            {n.pinned ? <Pin className="size-3 text-primary" aria-label="Pinned" /> : null}
            {n.bookmarked ? <Bookmark className="size-3 text-primary" aria-label="Bookmarked" /> : null}
            {n.following ? <Eye className="size-3 text-muted-foreground" aria-label="Following" /> : null}
            {n.muted ? <BellOff className="size-3 text-muted-foreground" aria-label="Muted" /> : null}
          </span>
        </div>
      </div>
    </div>
  );
});
