import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

export interface ErrorStateProps {
  title?: string;
  description?: string;
  /** Wired to a query's refetch. Omit to render without a retry affordance. */
  onRetry?: () => void;
  retryLabel?: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

/**
 * Reusable error state — the third of the loading/empty/error trio alongside
 * <LoadingState> and <EmptyState>. Announced politely so a failed background
 * refresh reaches a screen reader without stealing focus.
 */
export function ErrorState({
  title = "Something went wrong",
  description = "This couldn't be loaded. Try again in a moment.",
  onRetry,
  retryLabel = "Try again",
  action,
  className,
  compact,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-2 py-6" : "gap-3 py-12",
        className
      )}
    >
      <span
        className={cn(
          "inline-flex items-center justify-center rounded-full bg-destructive/10 text-destructive",
          compact ? "size-9" : "size-12"
        )}
      >
        <TriangleAlert className={compact ? "size-4" : "size-6"} aria-hidden="true" />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description ? <p className="mx-auto max-w-xs text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {action ?? (onRetry ? (
        <div className="pt-1">
          <Button variant="outline" size="sm" onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      ) : null)}
    </div>
  );
}
