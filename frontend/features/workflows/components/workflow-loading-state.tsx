import { Shimmer } from "@/components/ui/shimmer";
import { cn } from "@/lib/utils";

/**
 * The builder's loading shape: toolbar, three columns, status bar. It mirrors
 * the real layout so the page doesn't jump when the workflow arrives.
 */
export function WorkflowLoadingState({ className }: { className?: string }) {
  return (
    <div role="status" aria-label="Loading workflow" className={cn("flex h-full min-h-0 flex-col", className)}>
      <div className="flex h-14 shrink-0 items-center gap-2 border-b bg-card px-3">
        <Shimmer className="h-8 w-44" />
        <div className="ml-auto flex items-center gap-2">
          <Shimmer className="h-8 w-20" />
          <Shimmer className="h-8 w-16" />
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="hidden w-64 shrink-0 space-y-3 border-r bg-card p-3 lg:block">
          {Array.from({ length: 6 }).map((_, i) => (
            <Shimmer key={i} className="h-9" />
          ))}
        </div>

        <div className="min-w-0 flex-1 bg-background p-8">
          <div className="flex flex-wrap gap-8">
            {Array.from({ length: 4 }).map((_, i) => (
              <Shimmer key={i} className="h-[76px] w-52" />
            ))}
          </div>
        </div>

        <div className="hidden w-80 shrink-0 space-y-4 border-l bg-card p-4 lg:block">
          <Shimmer className="h-8" />
          <Shimmer className="h-20" />
          <Shimmer className="h-8" />
        </div>
      </div>

      <div className="h-9 shrink-0 border-t bg-card/40" />
    </div>
  );
}

/** Card grid placeholder, for the workflow list and the template browser. */
export function WorkflowCardGridLoading({ count = 6 }: { count?: number }) {
  return (
    <div role="status" aria-label="Loading" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className="h-44" />
      ))}
    </div>
  );
}
