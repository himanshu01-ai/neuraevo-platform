import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

/** Reusable empty state. Calm tone; never an error look. */
export function EmptyState({ icon: Icon, title, description, action, className, compact }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-2 py-6" : "gap-3 py-12",
        className
      )}
    >
      {Icon ? (
        <span
          className={cn(
            "inline-flex items-center justify-center rounded-full bg-muted text-muted-foreground",
            compact ? "size-9" : "size-12"
          )}
        >
          <Icon className={compact ? "size-4" : "size-6"} aria-hidden="true" />
        </span>
      ) : null}
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description ? <p className="mx-auto max-w-xs text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {action ? <div className="pt-1">{action}</div> : null}
    </div>
  );
}
