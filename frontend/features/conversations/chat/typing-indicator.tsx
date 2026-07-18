"use client";

import { Avatar } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

/**
 * The employee "typing" — three dots breathing while the scripted reply is in
 * flight. Pure animation over a pending mutation; nothing is being generated.
 * The dots use `animate-pulse`, which the global reduced-motion rule stills to
 * a static ellipsis.
 */
export function TypingIndicator({ employeeName, className }: { employeeName: string; className?: string }) {
  return (
    <div className={cn("flex items-end gap-2", className)} aria-label={`${employeeName} is typing`}>
      <Avatar name={employeeName} className="size-7 text-[0.625rem]" />
      <div className="rounded-2xl rounded-bl-sm border bg-card px-4 py-3 shadow-sm">
        <span className="flex items-center gap-1" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="size-1.5 animate-pulse rounded-full bg-muted-foreground"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </span>
      </div>
    </div>
  );
}
