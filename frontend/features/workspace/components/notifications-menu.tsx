"use client";

import { Bell, BellOff, Settings } from "lucide-react";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

/** Notifications dropdown. Empty by design (no backend); links to settings. */
export function NotificationsMenu({ className }: { className?: string }) {
  return (
    <DropdownMenu
      menuLabel="Notifications"
      align="end"
      className="w-80"
      header={
        <div className="-mx-1 -mt-1 mb-1">
          <div className="border-b px-4 py-3">
            <span className="text-sm font-semibold text-foreground">Notifications</span>
          </div>
          <div className="px-2 py-1">
            <EmptyState compact icon={BellOff} title="You're all caught up" description="New notifications appear here." />
          </div>
        </div>
      }
      items={[
        { key: "open", label: "Open notifications", icon: Bell, href: "/workspace/collaboration" },
        { key: "settings", label: "Notification settings", icon: Settings, href: "/workspace/settings" },
      ]}
      renderTrigger={(p) => (
        <button
          {...p}
          type="button"
          aria-label="Notifications"
          className={cn(
            "relative inline-flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            className
          )}
        >
          <Bell className="size-5" aria-hidden="true" />
        </button>
      )}
    />
  );
}
