"use client";

import { X } from "lucide-react";
import type { Attachment } from "@/services/conversations";
import { ATTACHMENT_KIND_META } from "../models/message-kinds";
import { cn } from "@/lib/utils";

export interface AttachmentChipProps {
  attachment: Attachment;
  /** Present only in the composer, where an attachment can still be unstaged. */
  onRemove?: (id: string) => void;
  className?: string;
}

/**
 * One attachment, as a compact chip: icon for the kind, name, and the size the
 * platform reports. Mock preview only — the chip is a description, not a file.
 */
export function AttachmentChip({ attachment, onRemove, className }: AttachmentChipProps) {
  const meta = ATTACHMENT_KIND_META[attachment.kind];
  const Icon = meta.icon;

  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs text-foreground",
        className
      )}
      title={attachment.preview ?? attachment.name}
    >
      <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="sr-only">{meta.label}: </span>
      <span className="truncate">{attachment.name}</span>
      <span className="shrink-0 text-muted-foreground">{attachment.size}</span>
      {onRemove ? (
        <button
          type="button"
          onClick={() => onRemove(attachment.id)}
          aria-label={`Remove ${attachment.name}`}
          className="ml-0.5 rounded-full p-0.5 text-muted-foreground transition-colors hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-3" aria-hidden="true" />
        </button>
      ) : null}
    </span>
  );
}

/** A message's attachments, wrapped under the bubble. */
export function AttachmentRow({ attachments, className }: { attachments: Attachment[]; className?: string }) {
  if (attachments.length === 0) return null;
  return (
    <ul className={cn("flex flex-wrap gap-1.5", className)} aria-label="Attachments">
      {attachments.map((attachment) => (
        <li key={attachment.id} className="min-w-0">
          <AttachmentChip attachment={attachment} />
        </li>
      ))}
    </ul>
  );
}
