"use client";

import { useSearchStore } from "@/store/memory";
import { ErrorState } from "@/components/ui/error-state";
import { useMemoryList } from "../hooks/use-memory";
import { MemoryCard } from "../components/memory-card";
import { MemoryCardGridLoading, MemoryEmptyState } from "../components/memory-states";
import { cn } from "@/lib/utils";

/**
 * What the current query matches.
 *
 * Results are in the order they're stored, not by relevance. This is a filter,
 * not a ranker — there is no score behind these rows, and sorting by one the UI
 * made up would be a claim nothing could back. The count is stated plainly so a
 * narrow result reads as a narrow result rather than a broken screen.
 */
export function SearchResults({ className }: { className?: string }) {
  const query = useSearchStore((s) => s.query);
  const list = useMemoryList(query);

  if (list.isPending) return <MemoryCardGridLoading className={className} />;

  if (list.isError) {
    return (
      <ErrorState
        title="Couldn't run that search"
        description="The knowledge couldn't be searched. Try again in a moment."
        onRetry={() => void list.refetch()}
        className={className}
      />
    );
  }

  if (list.data.length === 0) {
    return (
      <MemoryEmptyState
        title="Nothing matches"
        description="Try a different word, or loosen a filter."
        showActions={false}
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <p role="status" className="text-sm text-muted-foreground">
        <span className="font-medium tabular-nums text-foreground">{list.data.length}</span>{" "}
        {list.data.length === 1 ? "memory" : "memories"} match.
      </p>

      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {list.data.map((memory) => (
          <li key={memory.id}>
            <MemoryCard memory={memory} />
          </li>
        ))}
      </ul>
    </div>
  );
}
