"use client";

import Link from "next/link";
import { Menu } from "lucide-react";
import { ALL_NAV_ITEMS, MOBILE_PRIMARY_IDS } from "./nav-config";
import { useWorkspaceNav } from "../hooks/use-workspace-nav";
import { useSidebar } from "../hooks/use-sidebar";
import { cn } from "@/lib/utils";

const primaryItems = MOBILE_PRIMARY_IDS.flatMap((id) => {
  const item = ALL_NAV_ITEMS.find((i) => i.id === id);
  return item ? [item] : [];
});

/** Mobile bottom navigation: primary destinations + a "More" drawer trigger. */
export function BottomBar({ className }: { className?: string }) {
  const { isActive } = useWorkspaceNav();
  const { setMobileOpen } = useSidebar();

  return (
    <nav
      aria-label="Primary"
      className={cn("flex items-center justify-around border-t bg-card/80 backdrop-blur", className)}
    >
      {primaryItems.map((item) => {
        const Icon = item.icon;
        const active = isActive(item.href);
        return (
          <Link
            key={item.id}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-1 flex-col items-center gap-1 py-2 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active ? "text-primary" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="size-5" aria-hidden="true" />
            <span>{item.label}</span>
          </Link>
        );
      })}
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation menu"
        className="flex flex-1 flex-col items-center gap-1 py-2 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Menu className="size-5" aria-hidden="true" />
        <span>More</span>
      </button>
    </nav>
  );
}
