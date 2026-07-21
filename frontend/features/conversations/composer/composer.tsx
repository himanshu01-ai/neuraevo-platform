"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, SendHorizontal, Square } from "lucide-react";
import type { Attachment, MessageChannel, Suggestion } from "@/services/conversations";
import { useComposerStore } from "@/store/conversations";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip } from "@/components/ui/tooltip";
import { useConversationSuggestions, useSendMessage } from "../hooks/use-conversations";
import { useSpeechInput } from "../hooks/use-speech";
import { AttachmentChip } from "../attachments/attachment-chip";
import { SuggestionChips } from "../suggestions/suggestion-chips";
import { AttachMenu } from "./attach-menu";
import { MentionMenu } from "./mention-menu";
import { cn } from "@/lib/utils";

export interface ComposerProps {
  conversationId: string;
  employeeName: string;
  /** An archived conversation reads but doesn't write. */
  disabled?: boolean;
  className?: string;
}

/**
 * The composer: draft, attachments, mentions, suggestions, and voice input.
 * Enter sends, Shift+Enter breaks the line — the convention every chat surface
 * trains. Drafts live in the composer store keyed by conversation, so switching
 * threads never loses one.
 *
 * Voice is a first-class channel (Sprint 21): the mic dictates into the draft
 * via the browser's speech recognition, and a message sent from a dictated
 * draft is tagged `voice` so the transcript reads as a spoken turn in history.
 * Where the browser can't transcribe, the control disables itself and says so,
 * and the typed path is unaffected.
 */
/**
 * Stable fallback for the store selectors: `?? []` inline would mint a new
 * array every snapshot read, which React's `useSyncExternalStore` treats as a
 * changed store — an infinite re-render.
 */
const NO_ATTACHMENTS: Attachment[] = [];

export function Composer({ conversationId, employeeName, disabled = false, className }: ComposerProps) {
  const draft = useComposerStore((s) => s.drafts[conversationId] ?? "");
  const staged = useComposerStore((s) => s.staged[conversationId] ?? NO_ATTACHMENTS);
  const setDraft = useComposerStore((s) => s.setDraft);
  const clearDraft = useComposerStore((s) => s.clearDraft);
  const stageAttachment = useComposerStore((s) => s.stageAttachment);
  const unstageAttachment = useComposerStore((s) => s.unstageAttachment);
  const clearStaged = useComposerStore((s) => s.clearStaged);

  const suggestions = useConversationSuggestions(conversationId);
  const send = useSendMessage();
  const speech = useSpeechInput();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Whether the current draft came from speech. Set as dictation fills the
  // draft, cleared the moment the user types — so the channel reflects how the
  // message was actually composed, and resets with the conversation.
  const [spoken, setSpoken] = useState(false);
  useEffect(() => setSpoken(false), [conversationId]);

  // Pipe the live transcript into the draft while listening.
  useEffect(() => {
    if (speech.listening && speech.transcript) {
      setDraft(conversationId, speech.transcript);
      setSpoken(true);
    }
  }, [speech.listening, speech.transcript, conversationId, setDraft]);

  const canSend = !disabled && !send.isPending && draft.trim().length > 0;

  const handleSend = useCallback(() => {
    const content = draft.trim();
    if (!content || disabled || send.isPending) return;
    if (speech.listening) speech.stop();
    const channel: MessageChannel = spoken ? "voice" : "text";
    send.mutate(
      { id: conversationId, outgoing: { content, attachments: staged, channel } },
      {
        onSuccess: () => {
          clearDraft(conversationId);
          clearStaged(conversationId);
          setSpoken(false);
          speech.reset();
        },
      }
    );
  }, [draft, disabled, send, speech, spoken, conversationId, staged, clearDraft, clearStaged]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const insert = useCallback(
    (text: string) => {
      setDraft(conversationId, draft.length > 0 && !draft.endsWith(" ") ? `${draft} ${text}` : draft + text);
      textareaRef.current?.focus();
    },
    [conversationId, draft, setDraft]
  );

  const handleSuggestion = useCallback((suggestion: Suggestion) => insert(suggestion.insertText), [insert]);

  return (
    <div className={cn("border-t bg-card/60 px-4 py-3", className)}>
      <div className="mx-auto max-w-3xl space-y-2">
        <SuggestionChips suggestions={suggestions.data ?? []} onPick={handleSuggestion} />

        {staged.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Staged attachments">
            {staged.map((attachment) => (
              <li key={attachment.id} className="min-w-0">
                <AttachmentChip attachment={attachment} onRemove={(id) => unstageAttachment(conversationId, id)} />
              </li>
            ))}
          </ul>
        ) : null}

        <div className="flex items-end gap-2">
          <div className="flex shrink-0 items-center">
            <AttachMenu onAttach={(attachment) => stageAttachment(conversationId, attachment)} disabled={disabled} />
            <MentionMenu onMention={insert} disabled={disabled} />
          </div>

          <Textarea
            ref={textareaRef}
            rows={2}
            value={draft}
            onChange={(e) => {
              setDraft(conversationId, e.target.value);
              // Typing over a dictated draft makes it a text turn again.
              setSpoken(false);
            }}
            onKeyDown={handleKeyDown}
            placeholder={
              speech.listening
                ? "Listening… speak now"
                : disabled
                  ? "This conversation is archived."
                  : `Message ${employeeName}… (Enter to send, Shift+Enter for a new line)`
            }
            aria-label={`Message ${employeeName}`}
            disabled={disabled || send.isPending}
            className="max-h-40 min-h-[3.25rem] flex-1 resize-none"
          />

          <div className="flex shrink-0 items-center gap-1">
            <Tooltip
              side="top"
              content={
                !speech.supported
                  ? "Voice input isn't supported in this browser"
                  : speech.listening
                    ? "Stop dictation"
                    : "Speak your message"
              }
            >
              <span className="inline-flex">
                <Button
                  type="button"
                  variant={speech.listening ? "primary" : "ghost"}
                  size="icon"
                  disabled={disabled || !speech.supported || send.isPending}
                  onClick={() => (speech.listening ? speech.stop() : speech.start())}
                  aria-label={speech.listening ? "Stop dictation" : "Speak your message"}
                  aria-pressed={speech.listening}
                  className={cn(
                    "size-9",
                    speech.listening
                      ? "animate-pulse text-primary-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {speech.listening ? (
                    <Square className="size-4" aria-hidden="true" />
                  ) : (
                    <Mic className="size-4" aria-hidden="true" />
                  )}
                </Button>
              </span>
            </Tooltip>
            <Button
              type="button"
              size="icon"
              onClick={handleSend}
              disabled={!canSend}
              aria-label={`Send message to ${employeeName}`}
              className="size-9"
            >
              <SendHorizontal className="size-4" aria-hidden="true" />
            </Button>
          </div>
        </div>

        {send.isError ? (
          <p role="alert" className="text-xs text-destructive">
            {send.error instanceof Error ? send.error.message : "That message couldn't be sent."}
          </p>
        ) : speech.error ? (
          <p role="alert" className="text-xs text-destructive">
            {speech.error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
