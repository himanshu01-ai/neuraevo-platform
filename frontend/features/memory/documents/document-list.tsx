"use client";

import { useMemo } from "react";
import { EMPTY_SEARCH } from "@/services/memory";
import { ErrorState } from "@/components/ui/error-state";
import { useMemoryList } from "../hooks/use-memory";
import { MemoryCard } from "../components/memory-card";
import { MemoryCardGridLoading, MemoryEmptyState } from "../components/memory-states";
import { cn } from "@/lib/utils";

/**
 * The knowledge that arrived as a file rather than being learned.
 *
 * "Documents" here means the two kinds that come from something written down —
 * `document` and `artifact`. It's a view over the same knowledge, not a separate
 * store, so a document is also a memory and opens the same screens.
 *
 * The query runs unfiltered and narrows here rather than asking twice: two
 * `list` calls would be two cache entries of the same rows, and the frozen API
 * has no kind facet to push it down to anyway.
 */
export function DocumentList({ className }: { className?: string }) {
  const list = useMemoryList(EMPTY_SEARCH);

  const documents = useMemo(
    () => (list.data ?? []).filter((memory) => memory.kind === "document" || memory.kind === "artifact"),
    [list.data]
  );

  if (list.isPending) return <MemoryCardGridLoading className={className} />;

  if (list.isError) {
    return (
      <ErrorState
        title="Couldn't load documents"
        description="Your documents couldn't be loaded. Try again in a moment."
        onRetry={() => void list.refetch()}
        className={className}
      />
    );
  }

  if (documents.length === 0) {
    return (
      <MemoryEmptyState
        title="No documents yet"
        description="Import a file and it'll show up here as a memory."
        className={className}
      />
    );
  }

  return (
    <ul className={cn("grid gap-4 sm:grid-cols-2 xl:grid-cols-3", className)}>
      {documents.map((memory) => (
        <li key={memory.id}>
          <MemoryCard memory={memory} />
        </li>
      ))}
    </ul>
  );
}
