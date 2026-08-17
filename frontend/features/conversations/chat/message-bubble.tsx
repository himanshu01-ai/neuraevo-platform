"use client";

import { memo } from "react";
import { Mic, Square, Volume2 } from "lucide-react";
import type { ConversationMessage } from "@/services/conversations";
import { MESSAGE_ROLE_LABEL, READ_STATUS_LABEL } from "@/services/conversations";
import { Avatar } from "@/components/ui/avatar";
import { TONE_DOT } from "@/components/ui/status-badge";
import { formatTime } from "@/utils/format";
import { AttachmentRow } from "../attachments/attachment-chip";
import { ApprovalCard } from "../approvals/approval-card";
import { ArtifactCard } from "../artifacts/artifact-card";
import { ReferenceCard } from "../references/reference-card";
import { StreamingText } from "./streaming-text";
import type { MessageGroup } from "../hooks/use-message-groups";
import { cn } from "@/lib/utils";

/**
 * One run of messages from one author. User turns sit right in primary; the
 * employee's sit left on card surfaces; system messages centre as quiet pills.
 * Card kinds (approvals, artifacts, references) always arrive as their own
 * single-message group — `useMessageGroups` breaks runs on them.
 *
 * Memoized: the thread re-renders on every keystroke of the composer's parent,
 * and a settled group's props never change.
 */

export interface MessageBlockProps {
  group: MessageGroup;
  employeeName: string;
  /** The message currently playing its streaming reveal, if any. */
  streamingMessageId: string | null;
  onStreamingDone: () => void;
  selectedMessageId: string | null;
  onSelectMessage: (id: string | null) => void;
  onDecideApproval: (messageId: string, status: "APPROVED" | "REJECTED", comment: string) => void;
  isDeciding: boolean;
  /** Speak an assistant message aloud (browser text-to-speech). */
  onSpeak?: (text: string, id: string) => void;
  /** The message currently being spoken, if any. */
  speakingId?: string | null;
}

function CardBody({
  message,
  onDecideApproval,
  isDeciding,
}: Pick<MessageBlockProps, "onDecideApproval" | "isDeciding"> & { message: ConversationMessage }) {
  switch (message.kind) {
    case "approval_request":
      return message.approval ? (
        <ApprovalCard
          approval={message.approval}
          onDecide={(status, comment) => onDecideApproval(message.id, status, comment)}
          isDeciding={isDeciding}
        />
      ) : null;
    case "artifact":
      return message.artifact ? <ArtifactCard artifact={message.artifact} /> : null;
    case "workflow_reference":
      return message.workflowRef ? <ReferenceCard payload={{ kind: "workflow", workflow: message.workflowRef }} /> : null;
    case "task_reference":
      return message.taskRef ? <ReferenceCard payload={{ kind: "task", task: message.taskRef }} /> : null;
    case "memory_reference":
      return message.memoryRef ? <ReferenceCard payload={{ kind: "memory", memory: message.memoryRef }} /> : null;
    default:
      return null;
  }
}

export const MessageBlock = memo(function MessageBlock({
  group,
  employeeName,
  streamingMessageId,
  onStreamingDone,
  selectedMessageId,
  onSelectMessage,
  onDecideApproval,
  isDeciding,
  onSpeak,
  speakingId,
}: MessageBlockProps) {
  const first = group.messages[0];
  if (!first) return null;

  // System notifications centre as one quiet line — not a bubble, not a card.
  if (group.role === "system" && first.kind === "notification" && first.notification) {
    return (
      <div className="flex justify-center">
        <p className="inline-flex items-center gap-2 rounded-full border bg-muted/50 px-3 py-1 text-xs text-muted-foreground">
          <span aria-hidden="true" className={cn("size-1.5 rounded-full", TONE_DOT[first.notification.tone])} />
          {first.notification.headline}
          <time dateTime={first.createdAt}>{formatTime(first.createdAt)}</time>
        </p>
      </div>
    );
  }

  const isUser = group.role === "user";
  const authorName = isUser ? MESSAGE_ROLE_LABEL.user : group.role === "system" ? MESSAGE_ROLE_LABEL.system : employeeName;

  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      {!isUser ? <Avatar name={group.role === "system" ? "System" : employeeName} className="mt-6 size-7 shrink-0 text-[0.625rem]" /> : null}

      <div className={cn("flex min-w-0 max-w-[85%] flex-1 flex-col gap-1 sm:max-w-[75%]", isUser ? "items-end" : "items-start")}>
        <p className="px-1 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{authorName}</span>{" "}
          <time dateTime={first.createdAt}>{formatTime(first.createdAt)}</time>
        </p>

        {group.messages.map((message, index) => {
          const isCard = message.kind !== "text";
          const isLast = index === group.messages.length - 1;
          const isSelected = selectedMessageId === message.id;
          const isStreaming = streamingMessageId === message.id;

          if (isCard) {
            return (
              <div key={message.id} className="w-full space-y-1.5">
                {message.content ? <p className="px-1 text-sm text-muted-foreground">{message.content}</p> : null}
                <CardBody message={message} onDecideApproval={onDecideApproval} isDeciding={isDeciding} />
              </div>
            );
          }

          return (
            <div key={message.id} className={cn("flex min-w-0 flex-col gap-1", isUser ? "items-end" : "items-start")}>
              <button
                type="button"
                onClick={() => onSelectMessage(isSelected ? null : message.id)}
                aria-pressed={isSelected}
                aria-label={`Message from ${authorName} at ${formatTime(message.createdAt)}`}
                className={cn(
                  "whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-left text-sm shadow-sm transition-shadow",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isUser
                    ? "rounded-br-sm bg-primary text-primary-foreground"
                    : "rounded-bl-sm border bg-card text-foreground",
                  isSelected && "ring-2 ring-primary/40"
                )}
              >
                {isStreaming ? <StreamingText text={message.content} onDone={onStreamingDone} /> : message.content}
              </button>

              {message.attachments.length > 0 ? <AttachmentRow attachments={message.attachments} /> : null}

              <div className={cn("flex items-center gap-2 px-1", isUser ? "flex-row-reverse" : "flex-row")}>
                {message.channel === "voice" ? (
                  <span
                    className="inline-flex items-center gap-1 text-[0.65rem] text-muted-foreground"
                    title="Spoken message"
                  >
                    <Mic className="size-3" aria-hidden="true" />
                    Voice
                  </span>
                ) : null}

                {group.role === "assistant" && onSpeak ? (
                  <button
                    type="button"
                    onClick={() => onSpeak(message.content, message.id)}
                    aria-label={speakingId === message.id ? "Stop speaking" : "Read this reply aloud"}
                    className="inline-flex items-center gap-1 rounded-sm text-[0.65rem] text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {speakingId === message.id ? (
                      <Square className="size-3" aria-hidden="true" />
                    ) : (
                      <Volume2 className="size-3" aria-hidden="true" />
                    )}
                    {speakingId === message.id ? "Stop" : "Speak"}
                  </button>
                ) : null}

                {isUser && isLast ? (
                  <span className="text-[0.65rem] text-muted-foreground">{READ_STATUS_LABEL[message.readStatus]}</span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});
