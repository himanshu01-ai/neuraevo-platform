"use client";

import { memo, useCallback } from "react";
import { motion } from "framer-motion";
import type { MemorySummary } from "@/services/memory";
import { useMemoryStore, type MemoryViewMode } from "@/store/memory";
import { formatBytes, formatDate } from "@/utils/format";
import { MemoryCard } from "../components/memory-card";
import { MEMORY_KIND_META } from "../models/memory-kinds";
import { MemoryTypeBadge } from "../components/memory-badges";
import { cn } from "@/lib/utils";

/**
 * One memory, compactly — the browser's dense mode.
 *
 * The selection marker is one shared element (`layoutId`) rather than one per
 * row, so it slides from the old selection to the new instead of blinking.
 * Reduced motion collapses that to a cut via the global MotionConfig.
 */
const MemoryRow = memo(function MemoryRow({
  memory,
  isSelected,
  onSelect,
}: {
  memory: MemorySummary;
  isSelected: boolean;
  onSelect: (id: string) => void;
}) {
  const Icon = MEMORY_KIND_META[memory.kind].icon;

  return (
    <button
      type="button"
      onClick={() => onSelect(memory.id)}
      aria-pressed={isSelected}
      className={cn(
        "relative flex w-full items-start gap-3 overflow-hidden rounded-md border px-3 py-2.5 text-left transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isSelected ? "border-primary/40 bg-primary/5" : "border-transparent hover:bg-accent"
      )}
    >
      {isSelected ? (
        <motion.span
          layoutId="memory-selection"
          aria-hidden="true"
          className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary"
          transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        />
      ) : null}

      <span className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-sm bg-muted text-muted-foreground">
        <Icon className="size-3.5" aria-hidden="true" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{memory.title}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {memory.owner.employeeName} · {formatDate(memory.updatedAt)} · {formatBytes(memory.sizeBytes)}
        </span>
      </span>

      <MemoryTypeBadge memoryType={memory.memoryType} className="shrink-0" />
    </button>
  );
});

export interface MemoryListProps {
  memories: readonly MemorySummary[];
  viewMode: MemoryViewMode;
  className?: string;
}

/**
 * The browser's memory column.
 *
 * Both modes render the same memories, differing only in how much they say:
 * cards are roomy, rows are dense. The handler is `useCallback`-stable and the
 * items are memoized, so filtering or selecting re-renders the one item that
 * changed rather than the whole list.
 *
 * On virtualizing: the roster is bounded by what a query returns, and the
 * fixtures top out at fifteen. Virtualizing tens of rows costs a scroll
 * container, a measurement pass and a pile of absolute positioning to save
 * nothing. The frozen API caps `limit` at 100 and paginates with `offset`, so
 * the real answer at scale is that pagination — not a virtual window over a list
 * the server was never going to send whole.
 *
 * Rows animate in but not out. <AnimatePresence> would be the usual way to get
 * an exit, but framer-motion 11 and React 19 disagree about it badly enough that
 * filtered-out rows stay mounted (found and fixed the same way in Sprint 17.6).
 */
export function MemoryList({ memories, viewMode, className }: MemoryListProps) {
  const selectedMemoryId = useMemoryStore((s) => s.selectedMemoryId);
  const selectMemory = useMemoryStore((s) => s.selectMemory);

  const handleSelect = useCallback((id: string) => selectMemory(id), [selectMemory]);

  return (
    <ul className={cn(viewMode === "grid" ? "space-y-3" : "space-y-1", className)}>
      {memories.map((memory) => (
        <motion.li
          key={memory.id}
          layout="position"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          {viewMode === "grid" ? (
            <MemoryCard
              memory={memory}
              isSelected={selectedMemoryId === memory.id}
              onSelect={handleSelect}
            />
          ) : (
            <MemoryRow
              memory={memory}
              isSelected={selectedMemoryId === memory.id}
              onSelect={handleSelect}
            />
          )}
        </motion.li>
      ))}
    </ul>
  );
}
