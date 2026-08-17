"use client";

import type { ReactNode } from "react";
import { TopBar } from "@/features/workspace/components/top-bar";
import { WorkspaceStatus } from "@/features/workspace/components/workspace-status";
import { Sidebar } from "@/features/workspace/navigation/sidebar";
import { BottomBar } from "@/features/workspace/navigation/bottom-bar";
import { MobileDrawer } from "@/features/workspace/navigation/mobile-drawer";
import { useWorkspaceShortcuts } from "@/features/workspace/hooks/use-keyboard-shortcuts";

/**
 * The authenticated application shell. Fixed top bar + status bar with an
 * independently-scrolling main region between the sidebar (desktop) or bottom
 * bar + drawer (mobile). The full-viewport, overflow-hidden frame prevents
 * layout shift.
 */
export function WorkspaceShell({ children }: { children: ReactNode }) {
  useWorkspaceShortcuts();

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar className="hidden lg:flex" />
        <main id="workspace-main" className="min-w-0 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
      <WorkspaceStatus className="hidden lg:flex" />
      <BottomBar className="lg:hidden" />
      <MobileDrawer />
    </div>
  );
}
