"use client";

import { memo } from "react";
import { Pin, Users } from "lucide-react";
import type { ConversationSummary } from "@/services/conversations";
import { CONVERSATION_STATUS_LABEL, CONVERSATION_STATUS_TONE } from "@/services/conversations";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { TONE_DOT } from "@/components/ui/status-badge";
import { formatDate } from "@/utils/format";
import { cn } from "@/lib/utils";

export interface ConversationListItemProps {
  conversation: ConversationSummary;
  isSelected: boolean;
  onSelect: (id: string) => void;
}

/**
 * One conversation in the sidebar: who it's with, its title, the last line
 * said, when, and its standing — unread count, pin, shared mark, archived
 * state. The whole row is the select control; status is carried by a dot plus
 * text, never colour alone.
 */
export const ConversationListItem = memo(function ConversationListItem({
  conversation,
  isSelected,
  onSelect,
}: ConversationListItemProps) {
  const unread = conversation.unreadCount > 0;

  return (
    <button
      type="button"
      onClick={() => onSelect(conversation.id)}
      aria-pressed={isSelected}
      className={cn(
        "flex w-full items-start gap-3 rounded-lg border border-transparent p-3 text-left transition-colors",
        "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isSelected && "border-primary/40 bg-primary/5"
      )}
    >
      <Avatar name={conversation.employee.employeeName} className="mt-0.5" />

      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className={cn("truncate text-sm text-foreground", unread ? "font-semibold" : "font-medium")}>
            {conversation.title}
          </span>
          <time dateTime={conversation.updatedAt} className="shrink-0 text-xs text-muted-foreground">
            {formatDate(conversation.updatedAt)}
          </time>
        </span>

        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
          {conversation.employee.employeeName} · {conversation.lastMessagePreview}
        </span>

        <span className="mt-1.5 flex items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center gap-1 text-[0.65rem] text-muted-foreground"
            )}
          >
            <span aria-hidden="true" className={cn("size-1.5 rounded-full", TONE_DOT[CONVERSATION_STATUS_TONE[conversation.status]])} />
            {CONVERSATION_STATUS_LABEL[conversation.status]}
          </span>
          {conversation.pinned ? (
            <Pin className="size-3 text-primary" aria-label="Pinned" />
          ) : null}
          {conversation.shared ? (
            <Users className="size-3 text-muted-foreground" aria-label="Shared" />
          ) : null}
          {unread ? (
            <Badge variant="primary" className="ml-auto px-1.5 py-0 text-[0.65rem]">
              {conversation.unreadCount}
              <span className="sr-only"> unread</span>
            </Badge>
          ) : null}
        </span>
      </span>
    </button>
  );
});
