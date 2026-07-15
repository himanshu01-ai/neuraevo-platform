import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface WorkspaceCardProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  href?: string;
  onClick?: () => void;
  action?: ReactNode;
  className?: string;
  children?: ReactNode;
}

/** Reusable content card. Renders as a link/button when interactive (hover lift). */
export function WorkspaceCard({
  title,
  description,
  icon: Icon,
  href,
  onClick,
  action,
  className,
  children,
}: WorkspaceCardProps) {
  const interactive = Boolean(href || onClick);
  const classes = cn(
    "block rounded-lg border bg-card p-5 text-left shadow-sm transition-all",
    interactive &&
      "hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    className
  );

  const inner = (
    <>
      {Icon ? (
        <span className="mb-3 inline-flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="size-5" aria-hidden="true" />
        </span>
      ) : null}
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {description ? <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p> : null}
      {children}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={classes}>
        {inner}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cn(classes, "w-full")}>
        {inner}
      </button>
    );
  }
  return <div className={classes}>{inner}</div>;
}
