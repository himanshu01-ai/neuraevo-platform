import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "right" | "top";
  disabled?: boolean;
  className?: string;
}

/**
 * Lightweight CSS tooltip shown on hover/focus of its child (no portal). Used
 * for the collapsed sidebar. Pair with a visible or sr-only label so the
 * accessible name never depends on the tooltip alone.
 */
export function Tooltip({ content, children, side = "right", disabled, className }: TooltipProps) {
  if (disabled) return <>{children}</>;
  return (
    <span className={cn("group/tt relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-tooltip whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs font-medium text-popover-foreground opacity-0 shadow-md transition-opacity duration-150 group-hover/tt:opacity-100 group-focus-within/tt:opacity-100",
          side === "right" && "left-full top-1/2 ml-2 -translate-y-1/2",
          side === "top" && "bottom-full left-1/2 mb-2 -translate-x-1/2"
        )}
      >
        {content}
      </span>
    </span>
  );
}
