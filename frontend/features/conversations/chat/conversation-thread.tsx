"use client";

import { useCallback, useEffect, useRef } from "react";
import { MessageSquareText } from "lucide-react";
import type { ConversationMessage } from "@/services/conversations";
import { useConversationStore } from "@/store/conversations";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/utils/format";
import { useMessageGroups } from "../hooks/use-message-groups";
import { useDecideConversationApproval } from "../hooks/use-conversations";
import { MessageBlock } from "./message-bubble";
import { TypingIndicator } from "./typing-indicator";
import { cn } from "@/lib/utils";

export interface ConversationThreadProps {
  conversationId: string;
  messages: ConversationMessage[];
  employeeName: string;
  /** True while a send is in flight — the reply window the indicator fills. */
  isTyping: boolean;
  className?: string;
}

/**
 * The thread: day dividers, grouped turns, cards, the typing indicator, and
 * the streaming reveal on a fresh reply. The list stays pinned to the newest
 * message — on new content it follows, unless the reader has scrolled up to
 * history, which a chat must never yank away from.
 *
 * Long threads: rows are memoized blocks keyed by stable ids, and the fixture
 * threads stay well under the size where windowing pays for its complexity —
 * the seam for virtualisation is this one component, with no caller changes.
 */
export function ConversationThread({
  conversationId,
  messages,
  employeeName,
  isTyping,
  className,
}: ConversationThreadProps) {
  const sections = useMessageGroups(messages);
  const selectedMessageId = useConversationStore((s) => s.selectedMessageId);
  const selectMessage = useConversationStore((s) => s.selectMessage);
  const streamingMessageId = useConversationStore((s) => s.streamingMessageId);
  const setStreamingMessageId = useConversationStore((s) => s.setStreamingMessageId);
  const decide = useDecideConversationApproval();

  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedToEnd = useRef(true);

  // Track whether the reader is at the end *before* new content lands.
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    pinnedToEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedToEnd.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, isTyping, streamingMessageId]);

  // Entering a conversation always starts at its newest message.
  useEffect(() => {
    pinnedToEnd.current = true;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [conversationId]);

  const handleDecide = useCallback(
    (messageId: string, status: "APPROVED" | "REJECTED", comment: string) =>
      decide.mutate({ conversationId, messageId, status, comment }),
    [decide, conversationId]
  );

  const handleStreamingDone = useCallback(() => setStreamingMessageId(null), [setStreamingMessageId]);

  if (messages.length === 0 && !isTyping) {
    return (
      <div className={cn("flex items-center justify-center", className)}>
        <EmptyState
          icon={MessageSquareText}
          title="No messages yet"
          description={`Say hello — ${employeeName} is ready when you are.`}
        />
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className={cn("overflow-y-auto", className)}
      role="log"
      aria-label={`Conversation with ${employeeName}`}
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-4">
        {sections.map((section) => (
          <section key={section.day} aria-label={formatDate(`${section.day}T00:00:00Z`)}>
            <div className="mb-3 flex items-center gap-3" aria-hidden="true">
              <span className="h-px flex-1 bg-border" />
              <span className="text-xs font-medium text-muted-foreground">
                {formatDate(`${section.day}T00:00:00Z`)}
              </span>
              <span className="h-px flex-1 bg-border" />
            </div>
            <div className="flex flex-col gap-4">
              {section.groups.map((group, index) => (
                <MessageBlock
                  key={group.messages[0]?.id ?? `${section.day}_g${index}`}
                  group={group}
                  employeeName={employeeName}
                  streamingMessageId={streamingMessageId}
                  onStreamingDone={handleStreamingDone}
                  selectedMessageId={selectedMessageId}
                  onSelectMessage={selectMessage}
                  onDecideApproval={handleDecide}
                  isDeciding={decide.isPending}
                />
              ))}
            </div>
          </section>
        ))}

        {isTyping ? <TypingIndicator employeeName={employeeName} /> : null}
      </div>
    </div>
  );
}
