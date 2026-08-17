import { Shimmer } from "@/components/ui/shimmer";
import { cn } from "@/lib/utils";

/** Row placeholder, for the directory's task column. */
export function TaskListLoading({ count = 5, className }: { count?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading tasks" className={cn("space-y-2", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className="h-16" />
      ))}
    </div>
  );
}

/** Card placeholder, for the directory's roomy mode. */
export function TaskCardListLoading({ count = 3, className }: { count?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading tasks" className={cn("space-y-3", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className="h-44" />
      ))}
    </div>
  );
}

/**
 * The execution canvas's loading shape. It mirrors the real layout — a wide
 * graph area with a controls dock — so the page doesn't jump when the run
 * arrives.
 */
export function ExecutionGraphLoading({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading the execution graph"
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

/** The inspector's loading shape. */
export function TaskInspectorLoading({ className }: { className?: string }) {
  return (
    <div role="status" aria-label="Loading the inspector" className={cn("space-y-4", className)}>
      <Shimmer className="h-6 w-32" />
      <Shimmer className="h-2 w-full" />
      <Shimmer className="h-20" />
      <Shimmer className="h-28" />
    </div>
  );
}
