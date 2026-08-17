"use client";

import type { NotificationSummary } from "@/services/collaboration";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { Ellipsis } from "lucide-react";
import { QUICK_ACTION_META } from "../models/notification-meta";
import { cn } from "@/lib/utils";

export interface QuickActionsProps {
  notification: NotificationSummary;
  onToggle: (
    id: string,
    field: "read" | "archived" | "pinned" | "bookmarked" | "following" | "muted",
    value: boolean
  ) => void;
  disabled?: boolean;
  /** `menu` collapses into a dropdown (feed rows); `bar` lays the toggles out (inspector). */
  variant?: "menu" | "bar";
  className?: string;
}

/**
 * The quick actions a notification offers: mark read/unread, archive/restore,
 * pin, bookmark, follow, mute. Every one is a toggle whose label says what a
 * click will do, resolved from `QUICK_ACTION_META`. UI only — nothing is sent.
 *
 * On a feed row the set collapses into a menu so the row stays calm; in the
 * inspector it lays out as a bar of buttons.
 */
export function QuickActions({ notification, onToggle, disabled = false, variant = "menu", className }: QuickActionsProps) {
  const n = notification;

  const entries = [
    { field: "read" as const, active: n.read, meta: QUICK_ACTION_META.mark_read, destructive: false },
    { field: "pinned" as const, active: n.pinned, meta: QUICK_ACTION_META.pin, destructive: false },
    { field: "bookmarked" as const, active: n.bookmarked, meta: QUICK_ACTION_META.bookmark, destructive: false },
    { field: "following" as const, active: n.following, meta: QUICK_ACTION_META.follow, destructive: false },
    { field: "muted" as const, active: n.muted, meta: QUICK_ACTION_META.mute, destructive: false },
    { field: "archived" as const, active: n.archived, meta: QUICK_ACTION_META.archive, destructive: true },
  ];

  if (variant === "bar") {
    return (
      <div className={cn("flex flex-wrap gap-2", className)}>
        {entries.map(({ field, active, meta, destructive }) => {
          const Icon = active ? meta.activeIcon : meta.icon;
          return (
            <Button
              key={field}
              type="button"
              size="sm"
              variant="outline"
              disabled={disabled}
              onClick={() => onToggle(n.id, field, !active)}
              className={cn(active && "border-primary/40 bg-primary/5 text-primary", destructive && active && "text-foreground")}
            >
              <Icon className="size-4" aria-hidden="true" />
              {active ? meta.activeLabel : meta.label}
            </Button>
          );
        })}
      </div>
    );
  }

  return (
    <DropdownMenu
      menuLabel={`Actions for ${n.title}`}
      align="end"
      className={className}
      items={entries.map(({ field, active, meta, destructive }) => ({
        key: field,
        label: active ? meta.activeLabel : meta.label,
        icon: active ? meta.activeIcon : meta.icon,
        destructive: destructive && !active,
        onSelect: () => onToggle(n.id, field, !active),
      }))}
      renderTrigger={(props) => (
        <Button
          {...props}
          type="button"
          variant="ghost"
          size="icon"
          disabled={disabled}
          className="size-7 text-muted-foreground"
          aria-label={`Actions for ${n.title}`}
        >
          <Ellipsis className="size-4" aria-hidden="true" />
        </Button>
      )}
    />
  );
}
