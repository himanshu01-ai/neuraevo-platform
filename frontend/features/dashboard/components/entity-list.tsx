import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface EntityListItem {
  id: string;
  title: string;
  /** Secondary line. Inline content only — this renders inside a <span>. */
  meta?: ReactNode;
  /** Trailing slot, typically a <StatusBadge>. */
  trailing?: ReactNode;
  icon?: LucideIcon;
  /** Makes the row a link. Rows without one render as plain content. */
  href?: string;
  /** Marks the row as needing attention (unread, blocked, failed). */
  isHighlighted?: boolean;
}

export interface EntityListProps {
  items: EntityListItem[];
  /** Names the list for screen readers, e.g. "Recent tasks". */
  label: string;
  className?: string;
}

function Row({ item }: { item: EntityListItem }) {
  const Icon = item.icon;

  const inner = (
    <>
      {Icon ? (
        <span
          className={cn(
            "inline-flex size-8 shrink-0 items-center justify-center rounded-md transition-colors",
            item.isHighlighted ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="size-4" aria-hidden="true" />
        </span>
      ) : null}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{item.title}</span>
        {item.meta ? <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.meta}</span> : null}
      </span>
      {item.trailing ? <span className="shrink-0">{item.trailing}</span> : null}
    </>
  );

  const classes = "flex items-center gap-3 rounded-md px-2 py-2";

  if (item.href) {
    return (
      <Link
        href={item.href}
        className={cn(
          classes,
          "transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        )}
      >
        {inner}
      </Link>
    );
  }

  return <div className={classes}>{inner}</div>;
}

/**
 * The one list used by every "recent" section — tasks, workflows, approvals,
 * notifications, employees. Rows are uniform: optional icon, title, meta line,
 * and a trailing status slot.
 */
export function EntityList({ items, label, className }: EntityListProps) {
  return (
    <ul aria-label={label} className={cn("-mx-2 space-y-0.5", className)}>
      {items.map((item) => (
        <li key={item.id}>
          <Row item={item} />
        </li>
      ))}
    </ul>
  );
}
