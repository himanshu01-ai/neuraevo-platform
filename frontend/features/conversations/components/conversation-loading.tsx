import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Sidebar rows while the list loads. */
export function ConversationListLoading({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2 p-3", className)} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 rounded-lg p-2">
          <Skeleton className="size-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-3/4" />
            <Skeleton className="h-3 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Alternating bubbles while a thread loads. */
export function ThreadLoading({ className }: { className?: string }) {
  return (
    <div className={cn("mx-auto max-w-3xl space-y-4 px-4 py-6", className)} aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className={cn("flex", i % 2 === 0 ? "justify-start" : "justify-end")}>
          <Skeleton className={cn("h-14 rounded-2xl", i % 2 === 0 ? "w-2/3" : "w-1/2")} />
        </div>
      ))}
    </div>
  );
}

/** The context panel while a detail loads. */
export function ContextPanelLoading({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4 p-4", className)} aria-hidden="true">
      <Skeleton className="h-16 w-full rounded-lg" />
      <Skeleton className="h-24 w-full rounded-lg" />
      <Skeleton className="h-32 w-full rounded-lg" />
    </div>
  );
}
