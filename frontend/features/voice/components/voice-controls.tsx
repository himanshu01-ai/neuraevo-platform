"use client";

import { useState } from "react";
import { Mic, MicOff, SendHorizontal, Square, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import type { VoiceSession } from "../hooks/use-voice-session";
import { describeMode, shouldSpeakReplies } from "../lib/interaction-mode";
import { cn } from "@/lib/utils";

/**
 * Voice controls (Sprint 22): one obvious primary action — the mic — plus the
 * quiet toggles that switch interaction mode. A text field is always available
 * as the typed path (and the whole control set for the voice-disabled fallback).
 * Every control is a real button with an accessible label and keyboard focus.
 */
export interface VoiceControlsProps {
  session: VoiceSession;
  className?: string;
}

export function VoiceControls({ session, className }: VoiceControlsProps) {
  const [text, setText] = useState("");
  const {
    micActive,
    speaking,
    speechInputSupported,
    speechOutputSupported,
    mode,
    startListening,
    stopListening,
    stopSpeaking,
    submitText,
    toggleOutput,
  } = session;

  const canType = session.state !== "thinking" && session.state !== "executing";

  const handleSubmit = () => {
    const value = text.trim();
    if (!value) return;
    submitText(value);
    setText("");
  };

  return (
    <div className={cn("flex w-full max-w-xl flex-col items-center gap-3", className)}>
      {/* The typed path — always present; the sole input in the silent fallback. */}
      <form
        className="flex w-full items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
      >
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={speechInputSupported ? "Or type a message…" : "Type a message…"}
          aria-label="Type a message to the assistant"
          disabled={!canType}
        />
        <Button type="submit" size="icon" disabled={!canType || text.trim().length === 0} aria-label="Send message">
          <SendHorizontal className="size-4" aria-hidden="true" />
        </Button>
      </form>

      <div className="flex items-center gap-3">
        {/* Output toggle: keep speaking replies, or read them silently. */}
        <Tooltip
          side="top"
          content={
            !speechOutputSupported
              ? "Spoken replies aren't supported in this browser"
              : shouldSpeakReplies(mode)
                ? "Mute spoken replies"
                : "Speak replies aloud"
          }
        >
          <span className="inline-flex">
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={toggleOutput}
              disabled={!speechOutputSupported}
              aria-pressed={shouldSpeakReplies(mode)}
              aria-label={shouldSpeakReplies(mode) ? "Mute spoken replies" : "Speak replies aloud"}
              className="size-11 rounded-full"
            >
              {shouldSpeakReplies(mode) ? (
                <Volume2 className="size-5" aria-hidden="true" />
              ) : (
                <VolumeX className="size-5" aria-hidden="true" />
              )}
            </Button>
          </span>
        </Tooltip>

        {/* The primary action — big, central, and obviously the mic. */}
        {speaking ? (
          <Button
            type="button"
            onClick={stopSpeaking}
            aria-label="Stop speaking"
            className="size-16 rounded-full"
          >
            <Square className="size-6" aria-hidden="true" />
          </Button>
        ) : (
          <Tooltip
            side="top"
            content={
              !speechInputSupported
                ? "Voice input isn't supported in this browser"
                : micActive
                  ? "Stop listening"
                  : "Start listening"
            }
          >
            <span className="inline-flex">
              <Button
                type="button"
                onClick={micActive ? stopListening : startListening}
                disabled={!speechInputSupported}
                aria-pressed={micActive}
                aria-label={micActive ? "Stop listening" : "Start listening"}
                className={cn("size-16 rounded-full", micActive && "animate-pulse")}
              >
                {!speechInputSupported ? (
                  <MicOff className="size-6" aria-hidden="true" />
                ) : (
                  <Mic className="size-6" aria-hidden="true" />
                )}
              </Button>
            </span>
          </Tooltip>
        )}

        {/* Current interaction mode, stated plainly. */}
        <span
          className="hidden min-w-[6.5rem] text-xs text-muted-foreground sm:inline"
          aria-label={`Interaction mode: ${describeMode(mode)}`}
        >
          {describeMode(mode)}
        </span>
      </div>
    </div>
  );
}
