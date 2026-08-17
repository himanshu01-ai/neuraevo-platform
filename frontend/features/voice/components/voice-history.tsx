"use client";

import { Mic } from "lucide-react";
import type { ConversationMessage } from "@/services/conversations";
import { cn } from "@/lib/utils";

/**
 * The recent conversation, quietly present (Sprint 22). Voice is the focus, so
 * history sits to the side as a light record — enough to keep the thread of a
 * multi-turn exchange without competing with the orb. It reads the *same*
 * message cache the conversation workspace does, so nothing is duplicated and a
 * voice turn appears in both. Voice-origin turns are marked, as they are in the
 * text thread.
 */
export interface VoiceHistoryProps {
  messages: ConversationMessage[];
  employeeName: string;
  className?: string;
}

export function VoiceHistory({ messages, employeeName, className }: VoiceHistoryProps) {
  // Newest last; show the tail so the latest exchange is in view.
  const recent = messages.filter((m) => m.role !== "system").slice(-8);

  if (recent.length === 0) {
    return (
      <div className={cn("flex items-center justify-center p-6 text-center", className)}>
        <p className="text-sm text-muted-foreground">
          Your conversation with {employeeName} will appear here.
        </p>
      </div>
    );
  }

  return (
    <ol className={cn("space-y-3 overflow-y-auto p-4", className)} aria-label="Recent conversation">
      {recent.map((message) => {
        const isUser = message.role === "user";
        return (
          <li key={message.id} className={cn("flex flex-col gap-0.5", isUser ? "items-end" : "items-start")}>
            <span className="px-1 text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
              {isUser ? "You" : employeeName}
              {message.channel === "voice" ? (
                <Mic className="ml-1 inline size-3 align-[-1px]" aria-label="Spoken" />
              ) : null}
            </span>
            <span
              className={cn(
                "max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm shadow-sm",
                isUser
                  ? "rounded-br-sm bg-primary text-primary-foreground"
                  : "rounded-bl-sm border bg-card text-foreground"
              )}
            >
              {message.content}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
