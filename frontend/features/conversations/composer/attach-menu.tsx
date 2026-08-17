"use client";

import { Paperclip } from "lucide-react";
import type { Attachment } from "@/services/conversations";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { ATTACHMENT_KIND_META } from "../models/message-kinds";
import {
  ATTACHABLE_FILES,
  ATTACHABLE_MEMORIES,
  ATTACHABLE_TASKS,
  ATTACHABLE_WORKFLOWS,
} from "../models/mock-attachments";

export interface AttachMenuProps {
  /** Stages the pick on the next send. Mock only — nothing uploads. */
  onAttach: (attachment: Attachment) => void;
  disabled?: boolean;
}

/**
 * The composer's attach control: files (mock picks), and platform references —
 * workflow, task, memory. One menu, grouped by what each item is, every entry
 * staging a fixed reference the way a real picker would stage a file.
 */
export function AttachMenu({ onAttach, disabled = false }: AttachMenuProps) {
  const toItem = (attachment: Attachment) => ({
    key: attachment.id,
    label: attachment.name,
    icon: ATTACHMENT_KIND_META[attachment.kind].icon,
    onSelect: () => onAttach(attachment),
  });

  return (
    <DropdownMenu
      menuLabel="Attach"
      align="start"
      items={[
        ...ATTACHABLE_FILES.map(toItem),
        ...ATTACHABLE_WORKFLOWS.map(toItem),
        ...ATTACHABLE_TASKS.map(toItem),
        ...ATTACHABLE_MEMORIES.map(toItem),
      ]}
      renderTrigger={(props) => (
        <Button
          {...props}
          type="button"
          variant="ghost"
          size="icon"
          disabled={disabled}
          aria-label="Attach a file, workflow, task, or memory"
          className="size-9 text-muted-foreground"
        >
          <Paperclip className="size-4" aria-hidden="true" />
        </Button>
      )}
    />
  );
}
