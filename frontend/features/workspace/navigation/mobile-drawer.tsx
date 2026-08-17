"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { WorkspaceNavigation } from "./workspace-navigation";
import { useSidebar } from "../hooks/use-sidebar";
import { useWorkspaceNav } from "../hooks/use-workspace-nav";

/** Slide-out navigation drawer for mobile. Esc + scrim close; scroll locked. */
export function MobileDrawer() {
  const { mobileOpen, setMobileOpen } = useSidebar();
  const { groups, footer, isActive } = useWorkspaceNav();

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [mobileOpen, setMobileOpen]);

  return (
    <AnimatePresence>
      {mobileOpen ? (
        <motion.div
          className="fixed inset-0 z-modal lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <button
            aria-label="Close menu"
            tabIndex={-1}
            className="absolute inset-0 cursor-default bg-background/80 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <motion.div
            className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col border-r bg-card p-3 shadow-xl"
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="flex items-center justify-between px-1 pb-4 pt-1">
              <Logo variant="wordmark" href="/workspace" />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <WorkspaceNavigation
                groups={groups}
                footer={footer}
                isActive={isActive}
                onNavigate={() => setMobileOpen(false)}
              />
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
