"use client";

import Link from "next/link";
import type { NavItem as NavItemType } from "./nav-config";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface NavItemProps {
  item: NavItemType;
  active: boolean;
  collapsed?: boolean;
  onNavigate?: () => void;
}

/** A single sidebar/drawer link: icon + label, active/hover states, collapsed
 *  mode with tooltip. Label stays in the DOM (sr-only when collapsed). */
export function NavItem({ item, active, collapsed = false, onNavigate }: NavItemProps) {
  const Icon = item.icon;

  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        collapsed ? "w-full justify-center px-0" : "w-full",
        active ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
      )}
    >
      {active ? (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary"
        />
      ) : null}
      <Icon className={cn("size-5 shrink-0", active && "text-primary")} aria-hidden="true" />
      <span className={cn("truncate", collapsed && "sr-only")}>{item.label}</span>
    </Link>
  );

  return collapsed ? (
    <Tooltip content={item.label} side="right" className="w-full">
      {link}
    </Tooltip>
  ) : (
    link
  );
}
