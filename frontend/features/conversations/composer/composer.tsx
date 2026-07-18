"use client";

import { useCallback, useRef } from "react";
import { Mic, SendHorizontal } from "lucide-react";
import type { Attachment, Suggestion } from "@/services/conversations";
import { useComposerStore } from "@/store/conversations";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip } from "@/components/ui/tooltip";
import { useConversationSuggestions, useSendMessage } from "../hooks/use-conversations";
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
 * The composer: draft, attachments, mentions, suggestions, and the voice
 * placeholder. Enter sends, Shift+Enter breaks the line — the convention every
 * chat surface trains. Drafts live in the composer store keyed by
 * conversation, so switching threads never loses one.
 *
 * The mic is a placeholder on purpose: voice calling is Not Yet Implemented
 * platform scope, and a disabled control that says so beats a control that
 * pretends.
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = !disabled && !send.isPending && draft.trim().length > 0;

  const handleSend = useCallback(() => {
    const content = draft.trim();
    if (!content || disabled || send.isPending) return;
    send.mutate(
      { id: conversationId, outgoing: { content, attachments: staged } },
      {
        onSuccess: () => {
          clearDraft(conversationId);
          clearStaged(conversationId);
        },
      }
    );
  }, [draft, disabled, send, conversationId, staged, clearDraft, clearStaged]);

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
            onChange={(e) => setDraft(conversationId, e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? "This conversation is archived." : `Message ${employeeName}… (Enter to send, Shift+Enter for a new line)`}
            aria-label={`Message ${employeeName}`}
            disabled={disabled || send.isPending}
            className="max-h-40 min-h-[3.25rem] flex-1 resize-none"
          />

          <div className="flex shrink-0 items-center gap-1">
            <Tooltip side="top" content="Voice input arrives with the voice runtime — not yet available">
              <span className="inline-flex">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  disabled
                  aria-label="Voice input (not yet available)"
                  className="size-9 text-muted-foreground"
                >
                  <Mic className="size-4" aria-hidden="true" />
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
        ) : null}
      </div>
    </div>
  );
}
