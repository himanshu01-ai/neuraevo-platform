import type { ReactNode } from "react";
import { LoadingState } from "@/components/ui/loading-state";
import { cn } from "@/lib/utils";

export interface PanelProps {
  title?: ReactNode;
  description?: ReactNode;
  /** Row shown under the header (filters, tabs, segmented controls). */
  toolbar?: ReactNode;
  /** Header-right actions. */
  actions?: ReactNode;
  loading?: boolean;
  className?: string;
  bodyClassName?: string;
  children?: ReactNode;
}

/**
 * Reusable content container. Header (title/description/actions), optional
 * toolbar row, and a body that shows a loading state or its children (pass an
 * <EmptyState> as children for the empty case).
 */
export function Panel({
  title,
  description,
  toolbar,
  actions,
  loading = false,
  className,
  bodyClassName,
  children,
}: PanelProps) {
  const hasHeader = title || description || actions;

  return (
    <section className={cn("flex min-w-0 flex-col rounded-lg border bg-card shadow-sm", className)}>
      {hasHeader ? (
        <header className="flex items-start justify-between gap-3 border-b px-5 py-4">
          <div className="min-w-0 space-y-0.5">
            {title ? <h3 className="truncate text-sm font-semibold text-foreground">{title}</h3> : null}
            {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}

      {toolbar ? <div className="border-b px-5 py-2.5">{toolbar}</div> : null}

      <div className={cn("flex-1 p-5", bodyClassName)}>{loading ? <LoadingState rows={3} /> : children}</div>
    </section>
  );
}
