import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Feed rows while a feed loads. */
export function FeedLoading({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-3 rounded-lg border bg-card p-3">
          <Skeleton className="size-9 shrink-0 rounded-md" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-3/4" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** The inspector while a detail loads. */
export function InspectorLoading({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4 p-4", className)} aria-hidden="true">
      <Skeleton className="h-12 w-full rounded-lg" />
      <Skeleton className="h-24 w-full rounded-lg" />
      <Skeleton className="h-32 w-full rounded-lg" />
    </div>
  );
}
