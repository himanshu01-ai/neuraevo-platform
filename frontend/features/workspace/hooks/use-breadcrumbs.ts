"use client";

import { useMemo } from "react";
import { usePathname } from "next/navigation";
import { ALL_NAV_ITEMS } from "../navigation/nav-config";

export interface Crumb {
  label: string;
  href: string;
}

function titleCase(segment: string): string {
  return segment
    .split("-")
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

/** Breadcrumb trail derived from the pathname + nav labels. */
export function useBreadcrumbs(): Crumb[] {
  const pathname = usePathname();

  return useMemo(() => {
    const parts = pathname.split("/").filter(Boolean);
    const crumbs: Crumb[] = [];
    let acc = "";
    for (const part of parts) {
      acc += `/${part}`;
      const known = ALL_NAV_ITEMS.find((i) => i.href === acc);
      crumbs.push({ label: part === "workspace" ? "Workspace" : known?.label ?? titleCase(part), href: acc });
    }
    return crumbs;
  }, [pathname]);
}
