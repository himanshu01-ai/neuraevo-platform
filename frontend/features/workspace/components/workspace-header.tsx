import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface WorkspaceHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

/** Reusable page header for any workspace screen: title + description + actions. */
export function WorkspaceHeader({ title, description, actions, className }: WorkspaceHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0 space-y-1">
        <h1 className="truncate text-xl font-semibold tracking-tight text-foreground sm:text-2xl">{title}</h1>
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {/* Wraps rather than overflows: the employee profile carries four actions,
          which is more than a 375px row fits on one line. */}
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
