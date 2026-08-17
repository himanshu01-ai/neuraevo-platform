"use client";

import { useMemo, useRef } from "react";
import { Brain, ChevronRight } from "lucide-react";
import type { CollectionSummary, MemorySummary } from "@/services/memory";
import { useMemoryStore } from "@/store/memory";
import { COLLECTION_META } from "../models/collections";
import { cn } from "@/lib/utils";

export interface MemoryTreeProps {
  collections: readonly CollectionSummary[];
  /** The memories currently matching the query, for the per-shelf counts. */
  memories: readonly MemorySummary[];
  className?: string;
}

/**
 * The shelves, and how much is on each.
 *
 * A real `tree` widget: one tab stop for the whole thing, arrow keys to move
 * between shelves, Home/End to jump. That's the ARIA pattern for a tree, and it
 * matters here because a list of nine shelves shouldn't cost nine tab stops on
 * the way to the memories.
 *
 * The tree is one level deep. It's a `tree` rather than a `listbox` because the
 * shelves are a hierarchy — "All knowledge" is their parent — and because a
 * custom shelf's children are the natural next level for a later sprint.
 *
 * Two counts are shown deliberately: the shelf's total (what the platform says
 * is filed there) and, when a query is narrowing things, how many of those match
 * — so a shelf reading "0 of 4" tells you it isn't empty, your filter is.
 */
export function MemoryTree({ collections, memories, className }: MemoryTreeProps) {
  const selectedCollection = useMemoryStore((s) => s.selectedCollection);
  const selectCollection = useMemoryStore((s) => s.selectCollection);
  const treeRef = useRef<HTMLUListElement>(null);

  const matching = useMemo(() => {
    const counts = new Map<string, number>();
    memories.forEach((memory) => {
      counts.set(memory.collection, (counts.get(memory.collection) ?? 0) + 1);
    });
    return counts;
  }, [memories]);

  const total = collections.reduce((sum, c) => sum + c.count, 0);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    const keys = ["ArrowDown", "ArrowUp", "Home", "End"];
    if (!keys.includes(event.key)) return;
    event.preventDefault();

    const items = [...(treeRef.current?.querySelectorAll<HTMLElement>("[role='treeitem']") ?? [])];
    if (items.length === 0) return;
    const index = items.indexOf(document.activeElement as HTMLElement);

    const next =
      event.key === "Home"
        ? items[0]
        : event.key === "End"
          ? items[items.length - 1]
          : items[(index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length];
    next?.focus();
  };

  const rowClasses = (isActive: boolean) =>
    cn(
      "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      isActive ? "bg-primary/10 font-medium text-primary" : "text-foreground hover:bg-accent"
    );

  return (
    <ul
      ref={treeRef}
      role="tree"
      aria-label="Collections"
      onKeyDown={handleKeyDown}
      className={cn("space-y-0.5", className)}
    >
      {/* A tree contains treeitems and nothing else — a heading in the middle of
          one is a node the pattern has no meaning for, so the section label sits
          above the tree and the tree's own aria-label names it. */}
      <li role="none">
        <button
          type="button"
          role="treeitem"
          aria-selected={selectedCollection === null}
          // Roving tabindex: the tree is one stop, arrows move within it.
          tabIndex={selectedCollection === null ? 0 : -1}
          onClick={() => selectCollection(null)}
          className={rowClasses(selectedCollection === null)}
        >
          <Brain className="size-4 shrink-0" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate">All knowledge</span>
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{total}</span>
        </button>
      </li>

      {collections.map((entry) => {
        const meta = COLLECTION_META[entry.collection];
        const Icon = meta.icon;
        const isActive = selectedCollection === entry.collection;
        const matched = matching.get(entry.collection) ?? 0;
        const isNarrowed = matched !== entry.count;

        return (
          <li key={entry.collection} role="none">
            <button
              type="button"
              role="treeitem"
              aria-selected={isActive}
              tabIndex={isActive ? 0 : -1}
              onClick={() => selectCollection(isActive ? null : entry.collection)}
              className={rowClasses(isActive)}
            >
              <ChevronRight
                className={cn(
                  "size-3 shrink-0 text-muted-foreground transition-transform",
                  isActive && "rotate-90"
                )}
                aria-hidden="true"
              />
              <Icon className="size-4 shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{entry.name}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {isNarrowed ? (
                  <>
                    {matched} of {entry.count}
                    <span className="sr-only"> matching the current filters</span>
                  </>
                ) : (
                  entry.count
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
