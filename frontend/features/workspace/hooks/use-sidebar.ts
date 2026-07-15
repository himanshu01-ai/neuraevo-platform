"use client";

import { useUiStore } from "@/store/ui";
import { useMounted } from "@/hooks/use-mounted";

/**
 * Sidebar/drawer state. `collapsed` is gated on mount so the persisted
 * preference never causes a hydration mismatch (server + first client render
 * are always expanded, then it corrects).
 */
export function useSidebar() {
  const mounted = useMounted();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);
  const setCollapsed = useUiStore((s) => s.setSidebarCollapsed);
  const mobileOpen = useUiStore((s) => s.mobileNavOpen);
  const setMobileOpen = useUiStore((s) => s.setMobileNavOpen);

  return {
    collapsed: mounted ? collapsed : false,
    toggle,
    setCollapsed,
    mobileOpen,
    setMobileOpen,
  };
}
