"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useCollaborationCounts, useMarkAllRead } from "../hooks/use-collaboration";
import { COLLABORATION_TABS } from "../models/collaboration-tabs";
import { MARK_ALL_READ_ICON } from "../models/notification-meta";
import { cn } from "@/lib/utils";

export interface CollaborationHeaderProps {
  title: string;
  description: string;
  /** Extra actions beside "Mark all read". */
  actions?: ReactNode;
}

/**
 * The header across every collaboration screen: the title, the tab bar with
 * live count badges, and "Mark all read". The active tab is resolved from the
 * path so the same header drives navigation on all six screens without each
 * passing its own id. Counts are carried from the platform, never recomputed
 * here.
 */
export function CollaborationHeader({ title, description, actions }: CollaborationHeaderProps) {
  const pathname = usePathname();
  const counts = useCollaborationCounts();
  const markAllRead = useMarkAllRead();

  const countFor = (key: string | null): number | null => {
    if (!key || !counts.data) return null;
    const value = counts.data[key as keyof typeof counts.data];
    return value > 0 ? value : null;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h1 className="truncate text-xl font-semibold tracking-tight text-foreground sm:text-2xl">{title}</h1>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          <Button
            variant="outline"
            size="sm"
            onClick={() => markAllRead.mutate()}
            disabled={markAllRead.isPending || !counts.data || counts.data.unread === 0}
          >
            <MARK_ALL_READ_ICON className="size-4" aria-hidden="true" />
            Mark all read
          </Button>
        </div>
      </div>

      <nav aria-label="Collaboration sections" className="flex gap-1 overflow-x-auto border-b pb-px [scrollbar-width:thin]">
        {COLLABORATION_TABS.map((tab) => {
          const Icon = tab.icon;
          const active = pathname === tab.href;
          const count = countFor(tab.countKey);
          return (
            <Link
              key={tab.id}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-t-md border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {tab.label}
              {count !== null ? (
                <Badge variant={active ? "primary" : "default"} className="px-1.5 py-0 text-[0.65rem]">
                  {count}
                  <span className="sr-only"> items</span>
                </Badge>
              ) : null}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
