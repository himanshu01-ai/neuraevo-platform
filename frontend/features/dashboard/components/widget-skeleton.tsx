import { cn } from "@/lib/utils";

/**
 * Shimmering placeholder block. A sweep reads as "loading" more clearly than a
 * pulse on the dense widget surfaces; the global reduced-motion rule flattens it
 * to a static block.
 */
export function Shimmer({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cn("relative overflow-hidden rounded-md bg-muted", className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-foreground/10 to-transparent" />
    </div>
  );
}

/** Loading shape for a list-style widget: leading chip, title, meta line. */
export function WidgetSkeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading" className={cn("space-y-3", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Shimmer className="size-8 shrink-0" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <Shimmer className="h-3.5 w-1/2" />
            <Shimmer className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Loading shape for one overview card. The caller announces the loading state. */
export function MetricCardSkeleton() {
  return (
    <div aria-hidden="true" className="rounded-lg border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <Shimmer className="size-9" />
        <Shimmer className="h-5 w-16 rounded-full" />
      </div>
      <Shimmer className="mt-4 h-3 w-20" />
      <Shimmer className="mt-2 h-7 w-14" />
      <Shimmer className="mt-2 h-3 w-24" />
    </div>
  );
}
