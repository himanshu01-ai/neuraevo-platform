"use client";

import { type VoiceState } from "../lib/session-machine";
import { cn } from "@/lib/utils";

/**
 * The assistant's status line and live transcript (Sprint 22).
 *
 * This is the accessible heart of the experience: the orb is `aria-hidden`, so
 * the status is announced here via `aria-live` — every state change (Listening,
 * Thinking, Speaking…) reaches a screen reader as text. The live transcript
 * shows the user their own words forming, the feedback that makes dictation feel
 * responsive.
 */
export interface VoiceStatusProps {
  state: VoiceState;
  statusLabel: string;
  transcript: string;
  micActive: boolean;
  className?: string;
}

export function VoiceStatus({ state, statusLabel, transcript, micActive, className }: VoiceStatusProps) {
  const showTranscript = micActive && transcript.trim().length > 0;

  return (
    <div className={cn("flex flex-col items-center gap-3 text-center", className)}>
      <p
        aria-live="polite"
        className="flex items-center gap-2 text-sm font-medium tracking-wide text-muted-foreground"
      >
        {micActive ? (
          <span className="relative flex size-2.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
            <span className="relative inline-flex size-2.5 rounded-full bg-primary" />
          </span>
        ) : null}
        {statusLabel}
      </p>

      {/* The live transcript — reserved height so the layout doesn't jump. */}
      <p
        className={cn(
          "min-h-[2.5rem] max-w-xl text-balance text-lg text-foreground transition-opacity sm:text-xl",
          showTranscript ? "opacity-100" : "opacity-0"
        )}
        aria-hidden={!showTranscript}
      >
        {showTranscript ? `“${transcript}”` : " "}
      </p>
    </div>
  );
}
