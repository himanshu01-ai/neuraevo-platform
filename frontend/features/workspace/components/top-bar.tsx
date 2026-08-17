"use client";

import { Menu } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/layouts/theme-toggle";
import { Breadcrumbs } from "../navigation/breadcrumbs";
import { useSidebar } from "../hooks/use-sidebar";
import { SearchBar } from "./search-bar";
import { CommandButton } from "./command-button";
import { QuickActions } from "./quick-actions";
import { NotificationsMenu } from "./notifications-menu";
import { UserMenu } from "./user-menu";

/** Application top bar: brand, breadcrumbs, search, quick-create, and account. */
export function TopBar() {
  const { setMobileOpen } = useSidebar();

  return (
    <header className="z-header flex h-14 shrink-0 items-center gap-3 border-b bg-background/80 px-3 backdrop-blur sm:px-4">
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        aria-label="Open menu"
        className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
      >
        <Menu className="size-5" aria-hidden="true" />
      </button>

      <Logo variant="wordmark" href="/workspace" className="shrink-0" />

      <div className="ml-1 hidden min-w-0 items-center gap-2 md:flex">
        <span aria-hidden="true" className="text-muted-foreground/40">
          /
        </span>
        <Breadcrumbs className="min-w-0" />
      </div>

      <div className="flex-1" />

      <SearchBar className="hidden w-56 lg:flex xl:w-72" />

      <div className="flex items-center gap-1">
        <CommandButton className="lg:hidden" />
        <QuickActions />
        <ThemeToggle />
        <NotificationsMenu />
        <UserMenu />
      </div>
    </header>
  );
}
