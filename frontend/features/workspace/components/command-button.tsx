"use client";

import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

/** Compact command-palette / search trigger for small screens. */
export function CommandButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      aria-label="Search"
      className={cn(
        "inline-flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
    >
      <Search className="size-5" aria-hidden="true" />
    </button>
  );
}
