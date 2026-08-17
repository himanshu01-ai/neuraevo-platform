"use client";

import { motion, useReducedMotion } from "framer-motion";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { WorkspaceNavigation } from "./workspace-navigation";
import { useSidebar } from "../hooks/use-sidebar";
import { useWorkspaceNav } from "../hooks/use-workspace-nav";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Desktop collapsible sidebar. Width animates on collapse (reduced-motion safe). */
export function Sidebar({ className }: { className?: string }) {
  const { collapsed, toggle } = useSidebar();
  const { groups, footer, isActive } = useWorkspaceNav();
  const reduce = useReducedMotion();

  return (
    <motion.aside
      aria-label="Sidebar"
      animate={{ width: collapsed ? 68 : 248 }}
      transition={{ duration: reduce ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
      className={cn("relative flex shrink-0 flex-col border-r bg-card/40", className)}
    >
      <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden p-3">
        <WorkspaceNavigation groups={groups} footer={footer} isActive={isActive} collapsed={collapsed} />
      </div>
      <div className="border-t p-3">
        <Tooltip
          content="Expand sidebar"
          side="right"
          disabled={!collapsed}
          className={collapsed ? "w-full" : undefined}
        >
          <button
            type="button"
            onClick={toggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed && "justify-center px-0"
            )}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-5 shrink-0" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="size-5 shrink-0" aria-hidden="true" />
            )}
            <span className={cn("truncate", collapsed && "sr-only")}>Collapse</span>
          </button>
        </Tooltip>
      </div>
    </motion.aside>
  );
}
