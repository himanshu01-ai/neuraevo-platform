"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useBreadcrumbs } from "../hooks/use-breadcrumbs";
import { cn } from "@/lib/utils";

/** Route breadcrumb trail derived from the current pathname. */
export function Breadcrumbs({ className }: { className?: string }) {
  const crumbs = useBreadcrumbs();
  if (!crumbs.length) return null;

  return (
    <nav aria-label="Breadcrumb" className={cn("flex min-w-0 items-center", className)}>
      <ol className="flex min-w-0 items-center gap-1 text-sm">
        {crumbs.map((crumb, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={crumb.href} className="flex min-w-0 items-center gap-1">
              {i > 0 ? (
                <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/50" aria-hidden="true" />
              ) : null}
              {last ? (
                <span className="truncate font-medium text-foreground" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link
                  href={crumb.href}
                  className="truncate rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
