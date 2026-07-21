"use client";

import { CheckCircle2, Loader2 } from "lucide-react";
import { type ExecutionStatus } from "../hooks/use-voice-session";
import { cn } from "@/lib/utils";

/**
 * Background execution, shown live (Sprint 22). While the user stays in Voice
 * Mode, confirmed work runs through the real Task engine; this reports it —
 * "Send email…" then "Created TSK-1042" — so the user sees the platform acting,
 * not a spinner with no story. `aria-live` announces the progress for screen
 * readers.
 */
export interface VoiceExecutionProps {
  execution: ExecutionStatus;
  className?: string;
}

export function VoiceExecution({ execution, className }: VoiceExecutionProps) {
  return (
    <div
      aria-live="polite"
      className={cn(
        "inline-flex items-center gap-2 rounded-full border bg-card/90 px-3 py-1.5 text-sm shadow-sm backdrop-blur",
        className
      )}
    >
      {execution.active ? (
        <Loader2 className="size-4 animate-spin text-primary" aria-hidden="true" />
      ) : (
        <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
      )}
      <span className="text-foreground">{execution.label}</span>
    </div>
  );
}
