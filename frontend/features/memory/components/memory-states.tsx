import { Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Shimmer } from "@/components/ui/shimmer";
import { cn } from "@/lib/utils";

export interface MemoryEmptyStateProps {
  title?: string;
  description?: string;
  compact?: boolean;
  /** Hides the action where it'd be redundant. */
  showActions?: boolean;
  className?: string;
}

/**
 * The memory domain's empty state: <EmptyState> with the memory icon and the one
 * way out — bring knowledge in.
 */
export function MemoryEmptyState({
  title = "Nothing remembered yet",
  description = "What your AI employees learn shows up here. You can also import what they should already know.",
  compact,
  showActions = true,
  className,
}: MemoryEmptyStateProps) {
  return (
    <EmptyState
      compact={compact}
      className={className}
      icon={Brain}
      title={title}
      description={description}
      action={
        showActions ? (
          <Button size="sm" href="/workspace/memory/documents">
            Import knowledge
          </Button>
        ) : null
      }
    />
  );
}

/** Row placeholder, for the tree and the compact list. */
export function MemoryListLoading({ count = 6, className }: { count?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading memories" className={cn("space-y-2", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className="h-14" />
      ))}
    </div>
  );
}

/** Card placeholder, for the roomy mode and the collections grid. */
export function MemoryCardGridLoading({ count = 6, className }: { count?: number; className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading memories"
      className={cn("grid gap-4 sm:grid-cols-2 xl:grid-cols-3", className)}
    >
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className="h-56" />
      ))}
    </div>
  );
}

/**
 * The knowledge viewer's loading shape: a title block over a body of text. It
 * mirrors the real layout so the panel doesn't jump when the memory arrives.
 */
export function KnowledgeViewerLoading({ className }: { className?: string }) {
  return (
    <div role="status" aria-label="Loading memory" className={cn("space-y-4", className)}>
      <Shimmer className="h-6 w-2/3" />
      <div className="flex gap-2">
        <Shimmer className="h-5 w-24" />
        <Shimmer className="h-5 w-20" />
      </div>
      <Shimmer className="h-40" />
    </div>
  );
}

/** The inspector's loading shape. */
export function InspectorLoading({ className }: { className?: string }) {
  return (
    <div role="status" aria-label="Loading the inspector" className={cn("space-y-4", className)}>
      <Shimmer className="h-5 w-32" />
      <Shimmer className="h-24" />
      <Shimmer className="h-28" />
    </div>
  );
}

/**
 * The graph canvas's loading shape — a wide area with a controls dock, matching
 * the real thing.
 */
export function GraphLoading({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading the knowledge graph"
      className={cn("relative h-full min-h-64 overflow-hidden rounded-lg border bg-background p-6", className)}
    >
      <div className="flex flex-wrap gap-6">
        {Array.from({ length: 5 }).map((_, i) => (
          <Shimmer key={i} className="h-[76px] w-52" />
        ))}
      </div>
      <Shimmer className="absolute bottom-4 left-4 h-10 w-40" />
    </div>
  );
}
