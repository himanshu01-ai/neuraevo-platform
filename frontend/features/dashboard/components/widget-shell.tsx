"use client";

import { useId, type ReactNode } from "react";
import { ArrowRight, RefreshCw } from "lucide-react";
import { Panel } from "@/features/workspace/panels/panel";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { WidgetSkeleton } from "./widget-skeleton";
import { cn } from "@/lib/utils";

export interface WidgetShellProps {
  title: string;
  description?: string;
  /**
   * `panel` (default) puts the widget on a card, titled at h3 — the caller is
   * expected to group these under a section heading. `bare` renders its own
   * <section> titled at h2, for widgets whose body is already made of cards.
   */
  variant?: "panel" | "bare";
  /** Destination for the widget's full section. Renders a "View all" link. */
  href?: string;
  /** Extra header controls, shown before the refresh button. */
  action?: ReactNode;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  /** True while a refresh is in flight over data that is already on screen. */
  isRefreshing?: boolean;
  onRefresh?: () => void;
  /** Overrides the default skeleton when a widget needs its own shape. */
  loading?: ReactNode;
  empty: ReactNode;
  errorDescription?: string;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

/**
 * The one widget container. Owns the four states every dashboard widget must
 * support — loading, empty, error, ready — plus the refresh action, so no widget
 * re-implements them.
 *
 * State precedence: error, then first load, then empty, then ready. A refresh
 * that fails over data already on screen keeps the rows and reports through the
 * refresh button's busy state rather than blanking the widget.
 */
export function WidgetShell({
  title,
  description,
  variant = "panel",
  href,
  action,
  isLoading,
  isError,
  isEmpty,
  isRefreshing = false,
  onRefresh,
  loading,
  empty,
  errorDescription,
  className,
  bodyClassName,
  children,
}: WidgetShellProps) {
  const headingId = useId();

  // Titles are used verbatim in labels: lowercasing them would turn "AI
  // employees" into "ai employees", which screen readers say as a word.
  const body = isError ? (
    <ErrorState
      compact
      title={`Couldn't load ${title}`}
      description={errorDescription ?? "This widget couldn't be loaded. Try again in a moment."}
      onRetry={onRefresh}
    />
  ) : isLoading ? (
    (loading ?? <WidgetSkeleton />)
  ) : isEmpty ? (
    empty
  ) : (
    children
  );

  const actions = (
    <>
      {action}
      {href ? (
        <Button
          variant="ghost"
          size="icon"
          href={href}
          title={`View all ${title}`}
          aria-label={`View all ${title}`}
          className="size-8 text-muted-foreground hover:text-foreground"
        >
          <ArrowRight className="size-4" aria-hidden="true" />
        </Button>
      ) : null}
      {onRefresh ? (
        <Button
          variant="ghost"
          size="icon"
          onClick={onRefresh}
          title={`Refresh ${title}`}
          aria-label={`Refresh ${title}`}
          aria-busy={isRefreshing}
          className="size-8 text-muted-foreground hover:text-foreground"
        >
          <RefreshCw className={cn("size-4", isRefreshing && "animate-spin")} aria-hidden="true" />
        </Button>
      ) : null}
    </>
  );

  if (variant === "bare") {
    // A bare widget's ready/loading body is already made of cards, but its empty
    // and error states are bare text — give those a surface so they don't float.
    const needsSurface = isError || (!isLoading && isEmpty);

    return (
      <section aria-labelledby={headingId} className={className}>
        <div className="mb-4 flex items-end justify-between gap-3">
          <div className="min-w-0 space-y-0.5">
            <h2 id={headingId} className="text-sm font-semibold text-foreground">
              {title}
            </h2>
            {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        </div>
        <div className={cn(needsSurface ? "rounded-lg border bg-card shadow-sm" : bodyClassName)}>{body}</div>
      </section>
    );
  }

  return (
    <Panel
      title={title}
      description={description}
      className={cn("transition-shadow hover:shadow-md", className)}
      bodyClassName={bodyClassName}
      actions={actions}
    >
      {body}
    </Panel>
  );
}
