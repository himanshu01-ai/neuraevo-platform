"use client";

import { useEffect } from "react";
import { useUiStore } from "@/store/ui";

/** Global workspace shortcuts. Ignored while typing in a field. */
export function useWorkspaceShortcuts() {
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const typing =
        !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
      if (typing) return;

      // Cmd/Ctrl+B toggles the sidebar.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleSidebar]);
}
