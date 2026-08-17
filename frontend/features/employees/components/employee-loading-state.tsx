import { Shimmer } from "@/components/ui/shimmer";
import { cn } from "@/lib/utils";

/** Card grid placeholder, for the directory and the template browser. */
export function EmployeeCardGridLoading({ count = 6, className }: { count?: number; className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading employees"
      className={cn("grid gap-4 sm:grid-cols-2 xl:grid-cols-3", className)}
    >
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className="h-56" />
      ))}
    </div>
  );
}

/** Row placeholder, for the directory's list column. */
export function EmployeeListLoading({ count = 5, className }: { count?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading employees" className={cn("space-y-2", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className="h-16" />
      ))}
    </div>
  );
}

/**
 * The profile's loading shape: identity block, then two stacked sections. It
 * mirrors the real layout so the panel doesn't jump when the employee arrives.
 */
export function EmployeeProfileLoading({ className }: { className?: string }) {
  return (
    <div role="status" aria-label="Loading employee" className={cn("space-y-6", className)}>
      <div className="flex items-center gap-4">
        <Shimmer className="size-14 rounded-full" />
        <div className="min-w-0 flex-1 space-y-2">
          <Shimmer className="h-5 w-48" />
          <Shimmer className="h-4 w-32" />
        </div>
      </div>
      <Shimmer className="h-32" />
      <Shimmer className="h-40" />
    </div>
  );
}
