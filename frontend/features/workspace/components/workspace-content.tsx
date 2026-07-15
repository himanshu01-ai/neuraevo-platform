import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Centered, padded content wrapper for the main workspace region. */
export function WorkspaceContent({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("mx-auto w-full max-w-[90rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8", className)}>
      {children}
    </div>
  );
}
