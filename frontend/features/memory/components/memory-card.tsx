"use client";

import { memo } from "react";
import Link from "next/link";
import { Bot, SquareArrowOutUpRight, Workflow } from "lucide-react";
import { LANGUAGE_LABEL, type MemorySummary } from "@/services/memory";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { formatBytes, formatDate } from "@/utils/format";
import { collectionLabel } from "../models/collections";
import { MEMORY_KIND_META } from "../models/memory-kinds";
import { MemoryStatusBadge, MemoryTypeBadge } from "./memory-badges";
import { cn } from "@/lib/utils";

export interface MemoryCardProps {
  memory: MemorySummary;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
  /** Link counts, which only the detail carries. Omit where unknown. */
  linkedEmployees?: number;
  linkedWorkflows?: number;
}

/**
 * One memory at a glance: what it is, where it's filed, who owns it, and
 * everything the workspace promises about it.
 *
 * The card body is a button, not a link: selecting a memory fills the viewer
 * beside it rather than navigating. The "open" link sits outside that button so
 * its click isn't swallowed.
 *
 * Dates are formatted through `utils/format`, which pins the locale and the time
 * zone — an unpinned `toLocaleDateString` would render one string on the server
 * and another in the browser, and this card renders on both.
 */
export const MemoryCard = memo(function MemoryCard({
  memory,
  isSelected = false,
  onSelect,
  linkedEmployees,
  linkedWorkflows,
}: MemoryCardProps) {
  const kind = MEMORY_KIND_META[memory.kind];
  const KindIcon = kind.icon;

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-lg border bg-card p-4 shadow-sm transition-all",
        "hover:border-primary/30 hover:shadow-md",
        isSelected && "border-primary/50 ring-2 ring-primary/30"
      )}
    >
      <div className="flex items-start gap-3">
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <KindIcon className="size-4" aria-hidden="true" />
        </span>

        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-foreground">
            {onSelect ? (
              // Stretched over the card so the whole surface selects, while the
              // open link stays clickable above it.
              <button
                type="button"
                onClick={() => onSelect(memory.id)}
                aria-pressed={isSelected}
                className="rounded-sm text-left after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {memory.title}
              </button>
            ) : (
              memory.title
            )}
          </h3>
          <p className="truncate text-xs text-muted-foreground">
            {kind.label} · {collectionLabel(memory.collection, memory.customCollection)}
          </p>
        </div>

        <Link
          href={`/workspace/memory/${memory.id}`}
          aria-label={`Open ${memory.title}`}
          className="relative z-10 inline-flex size-7 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <SquareArrowOutUpRight className="size-4" aria-hidden="true" />
        </Link>
      </div>

      <p className="mt-3 line-clamp-2 flex-1 text-sm text-muted-foreground">{memory.summary}</p>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <MemoryTypeBadge memoryType={memory.memoryType} />
        <MemoryStatusBadge status={memory.status} />
        <Badge variant="outline">{LANGUAGE_LABEL[memory.language]}</Badge>
      </div>

      {memory.tags.length > 0 ? (
        <ul className="mt-2 flex flex-wrap items-center gap-1">
          {memory.tags.map((tag) => (
            <li
              key={tag}
              className="inline-flex items-center rounded-sm bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
            >
              <span className="sr-only">Tag: </span>#{tag}
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="mt-3 space-y-1.5 border-t pt-3 text-xs">
        <div className="flex items-center justify-between gap-2">
          <dt className="flex items-center gap-1.5 text-muted-foreground">
            <Avatar name={memory.owner.employeeName} className="size-4 text-[0.5rem]" />
            <span className="sr-only">Owner: </span>
            {memory.owner.employeeName}
          </dt>
          <dd className="shrink-0 tabular-nums text-muted-foreground">{formatBytes(memory.sizeBytes)}</dd>
        </div>

        <div className="flex items-center justify-between gap-2 text-muted-foreground">
          <dt>Created</dt>
          <dd className="tabular-nums">{formatDate(memory.createdAt)}</dd>
        </div>
        <div className="flex items-center justify-between gap-2 text-muted-foreground">
          <dt>Updated</dt>
          <dd className="tabular-nums">{formatDate(memory.updatedAt)}</dd>
        </div>

        {linkedEmployees !== undefined || linkedWorkflows !== undefined ? (
          <div className="flex items-center gap-3 pt-0.5 text-muted-foreground">
            {linkedEmployees !== undefined ? (
              <span className="flex items-center gap-1">
                <Bot className="size-3.5 shrink-0" aria-hidden="true" />
                {linkedEmployees}
                <span className="sr-only"> linked employees</span>
              </span>
            ) : null}
            {linkedWorkflows !== undefined ? (
              <span className="flex items-center gap-1">
                <Workflow className="size-3.5 shrink-0" aria-hidden="true" />
                {linkedWorkflows}
                <span className="sr-only"> linked workflows</span>
              </span>
            ) : null}
          </div>
        ) : null}
      </dl>
    </div>
  );
});
