"use client";

import { useMemo } from "react";
import { usePathname } from "next/navigation";
import { NAV_GROUPS, NAV_FOOTER } from "../navigation/nav-config";

/** Memoized navigation model + active-route matcher for the current pathname. */
export function useWorkspaceNav() {
  const pathname = usePathname();

  const isActive = useMemo(() => {
    return (href: string) => {
      if (href === "/workspace") return pathname === "/workspace";
      return pathname === href || pathname.startsWith(`${href}/`);
    };
  }, [pathname]);

  return useMemo(
    () => ({ groups: NAV_GROUPS, footer: NAV_FOOTER, isActive, pathname }),
    [isActive, pathname]
  );
}
