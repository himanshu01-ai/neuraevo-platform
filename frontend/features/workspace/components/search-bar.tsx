"use client";

import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Global search / command-palette trigger. Presentational for now — the palette
 * itself is a later sprint; this is the reusable entry point in the top bar.
 */
export function SearchBar({ className }: { className?: string }) {
  return (
    <button
      type="button"
      aria-label="Search"
      className={cn(
        "flex h-9 w-full items-center gap-2 rounded-md border border-input bg-background px-3 text-sm text-muted-foreground transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
    >
      <Search className="size-4 shrink-0" aria-hidden="true" />
      <span className="flex-1 text-left">Search workspace…</span>
      <kbd className="hidden rounded border bg-muted px-1.5 font-mono text-[10px] text-muted-foreground sm:inline">
        ⌘K
      </kbd>
    </button>
  );
}
