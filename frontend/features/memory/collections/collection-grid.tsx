"use client";

import { memo } from "react";
import { useRouter } from "next/navigation";
import type { CollectionSummary } from "@/services/memory";
import { useMemoryStore } from "@/store/memory";
import { ErrorState } from "@/components/ui/error-state";
import { Progress } from "@/components/ui/progress";
import { formatBytes } from "@/utils/format";
import { useCollections } from "../hooks/use-memory";
import { COLLECTION_META } from "../models/collections";
import { MemoryCardGridLoading } from "../components/memory-states";
import { cn } from "@/lib/utils";

/** One shelf: what it's for, how much is on it, and its share of the whole. */
const CollectionCard = memo(function CollectionCard({
  entry,
  share,
  onOpen,
}: {
  entry: CollectionSummary;
  share: number;
  onOpen: (collection: CollectionSummary["collection"]) => void;
}) {
  const Icon = COLLECTION_META[entry.collection].icon;
  const isEmpty = entry.count === 0;

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-lg border bg-card p-5 shadow-sm transition-all",
        "hover:border-primary/30 hover:shadow-md",
        isEmpty && "border-dashed"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span
          className={cn(
            "inline-flex size-9 items-center justify-center rounded-md",
            isEmpty ? "bg-muted text-muted-foreground" : "bg-primary/10 text-primary"
          )}
        >
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
          {formatBytes(entry.sizeBytes)}
        </span>
      </div>

      <h3 className="mt-4 text-sm font-semibold text-foreground">
        <button
          type="button"
          onClick={() => onOpen(entry.collection)}
          className="rounded-sm text-left after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {entry.name}
        </button>
      </h3>
      <p className="mt-1 flex-1 text-sm leading-relaxed text-muted-foreground">{entry.description}</p>

      <div className="mt-4 border-t pt-3">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="text-muted-foreground">
            {entry.count} {entry.count === 1 ? "memory" : "memories"}
          </span>
          <span className="tabular-nums text-muted-foreground">{Math.round(share * 100)}%</span>
        </div>
        <Progress
          value={share * 100}
          label={`${entry.name}: ${entry.count} memories`}
          className="mt-1.5"
        />
      </div>
    </div>
  );
});

/**
 * Every shelf in the workspace.
 *
 * Opening one selects it in the tree and takes you to the browser — a collection
 * isn't a separate place, it's a filter on the same knowledge, and pretending
 * otherwise would give the user two mental models of one thing.
 *
 * Empty shelves are shown rather than hidden: knowing a shelf exists and has
 * nothing on it is what tells you where to put the next thing.
 */
export function CollectionGrid({ className }: { className?: string }) {
  const router = useRouter();
  const query = useCollections();
  const selectCollection = useMemoryStore((s) => s.selectCollection);

  if (query.isPending) return <MemoryCardGridLoading className={className} />;

  if (query.isError) {
    return (
      <ErrorState
        title="Couldn't load collections"
        description="Your collections couldn't be loaded. Try again in a moment."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  const total = query.data.reduce((sum, c) => sum + c.count, 0);

  const handleOpen = (collection: CollectionSummary["collection"]) => {
    selectCollection(collection);
    router.push("/workspace/memory");
  };

  return (
    <div className={cn("grid gap-4 sm:grid-cols-2 xl:grid-cols-3", className)}>
      {query.data.map((entry) => (
        <CollectionCard
          key={entry.collection}
          entry={entry}
          share={total === 0 ? 0 : entry.count / total}
          onOpen={handleOpen}
        />
      ))}
    </div>
  );
}
