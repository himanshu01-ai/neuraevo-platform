import { Skeleton } from "./skeleton";
import { Spinner } from "./spinner";
import { cn } from "@/lib/utils";

export interface LoadingStateProps {
  variant?: "skeleton" | "spinner";
  rows?: number;
  label?: string;
  className?: string;
}

/** Reusable loading placeholder. Skeleton rows by default; spinner on request. */
export function LoadingState({ variant = "skeleton", rows = 3, label = "Loading", className }: LoadingStateProps) {
  if (variant === "spinner") {
    return (
      <div
        role="status"
        className={cn("flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground", className)}
      >
        <Spinner />
        <span>{label}…</span>
      </div>
    );
  }

  return (
    <div role="status" aria-label={label} className={cn("space-y-3 py-2", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-4" style={{ width: `${Math.max(40, 92 - i * 14)}%` }} />
      ))}
    </div>
  );
}
