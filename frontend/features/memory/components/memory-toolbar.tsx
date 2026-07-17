"use client";

import { useState } from "react";
import { ChevronDown, Folder, Import, LayoutGrid, List, Search, SlidersHorizontal, X } from "lucide-react";
import { activeFacetCount, hasActiveSearch, useSearchStore } from "@/store/memory";
import { useMemoryStore, type MemoryViewMode } from "@/store/memory";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchPanel } from "../search/search-panel";
import { cn } from "@/lib/utils";

const VIEW_MODES: { mode: MemoryViewMode; label: string; icon: typeof LayoutGrid }[] = [
  { mode: "grid", label: "Cards", icon: LayoutGrid },
  { mode: "list", label: "Compact", icon: List },
];

/**
 * The workspace's top bar: search, filters, import and collections.
 *
 * The keyword box lives here because searching is the first thing you do; the
 * rest of the facets fold away behind a real disclosure, because eight controls
 * across the top of a three-column layout would leave no room for the layout.
 * The chip shows how many facets are on, so a filtered view never looks like an
 * empty one.
 */
export function MemoryToolbar({ className }: { className?: string }) {
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);

  const query = useSearchStore((s) => s.query);
  const setKeyword = useSearchStore((s) => s.setKeyword);
  const reset = useSearchStore((s) => s.reset);

  const viewMode = useMemoryStore((s) => s.viewMode);
  const setViewMode = useMemoryStore((s) => s.setViewMode);

  const isFiltered = hasActiveSearch(query);
  const facets = activeFacetCount(query);

  return (
    <div className={cn("rounded-lg border bg-card p-3 shadow-sm", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1 sm:max-w-80">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            value={query.keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Search knowledge"
            aria-label="Search knowledge"
            className="h-9 pl-9"
          />
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsFiltersOpen((open) => !open)}
          aria-expanded={isFiltersOpen}
          aria-controls="memory-filters"
        >
          <SlidersHorizontal className="size-4" aria-hidden="true" />
          Filters
          {facets > 0 ? <Badge variant="primary">{facets}</Badge> : null}
          <ChevronDown
            className={cn("size-4 transition-transform", isFiltersOpen && "rotate-180")}
            aria-hidden="true"
          />
        </Button>

        {isFiltered ? (
          <Button variant="ghost" size="sm" onClick={reset}>
            <X className="size-4" aria-hidden="true" />
            Clear
          </Button>
        ) : null}

        <span aria-hidden="true" className="mx-1 hidden h-5 w-px bg-border sm:block" />

        <Button variant="outline" size="sm" href="/workspace/memory/documents">
          <Import className="size-4" aria-hidden="true" />
          Import
        </Button>

        <Button variant="outline" size="sm" href="/workspace/memory/collections">
          <Folder className="size-4" aria-hidden="true" />
          Collections
        </Button>

        <div
          role="group"
          aria-label="View mode"
          className="ml-auto flex shrink-0 items-center gap-0.5 rounded-md border bg-background p-0.5"
        >
          {VIEW_MODES.map(({ mode, label, icon: Icon }) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              aria-pressed={viewMode === mode}
              className={cn(
                "inline-flex size-7 items-center justify-center rounded-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                viewMode === mode
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              <span className="sr-only">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {isFiltersOpen ? (
        <div id="memory-filters" className="mt-3 border-t pt-3">
          <SearchPanel layout="inline" />
        </div>
      ) : null}
    </div>
  );
}
