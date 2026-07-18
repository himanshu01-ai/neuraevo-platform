"use client";

import { AtSign } from "lucide-react";
import { EMPLOYEE_LIST } from "@/services/conversations";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { MESSAGE_KIND_META, SUGGESTION_KIND_META } from "../models/message-kinds";

export interface MentionMenuProps {
  /** Writes the mention into the draft at the caret. Mock only. */
  onMention: (text: string) => void;
  disabled?: boolean;
}

/** The platform records a mention can point at, beyond employees. */
const RECORD_MENTIONS = [
  { key: "wf_1", label: "#workflow Weekly competitor brief", icon: MESSAGE_KIND_META.workflow_reference.icon, insert: "#workflow(Weekly competitor brief) " },
  { key: "wf_2", label: "#workflow Market signal digest", icon: MESSAGE_KIND_META.workflow_reference.icon, insert: "#workflow(Market signal digest) " },
  { key: "tk_1", label: "#task TASK-1001", icon: MESSAGE_KIND_META.task_reference.icon, insert: "#task(TASK-1001) " },
  { key: "tk_2", label: "#task TASK-1004", icon: MESSAGE_KIND_META.task_reference.icon, insert: "#task(TASK-1004) " },
  { key: "mem_1", label: "#memory Competitor A pricing move", icon: MESSAGE_KIND_META.memory_reference.icon, insert: "#memory(Competitor A moved to per-seat pricing) " },
  { key: "mem_4", label: "#memory House voice rules", icon: MESSAGE_KIND_META.memory_reference.icon, insert: "#memory(House voice: sentence case, never title case) " },
];

/**
 * The composer's mention control: @ an AI employee, or # a workflow, task, or
 * memory. Picking one writes plain text into the draft — resolution to a real
 * reference is Sprint 18's, and the syntax is designed to survive the swap.
 */
export function MentionMenu({ onMention, disabled = false }: MentionMenuProps) {
  return (
    <DropdownMenu
      menuLabel="Mention"
      align="start"
      items={[
        ...EMPLOYEE_LIST.map((employee) => ({
          key: employee.employeeId,
          label: `@${employee.employeeName} — ${employee.roleTitle}`,
          icon: SUGGESTION_KIND_META.employee.icon,
          onSelect: () => onMention(`@${employee.employeeName} `),
        })),
        ...RECORD_MENTIONS.map((record) => ({
          key: record.key,
          label: record.label,
          icon: record.icon,
          onSelect: () => onMention(record.insert),
        })),
      ]}
      renderTrigger={(props) => (
        <Button
          {...props}
          type="button"
          variant="ghost"
          size="icon"
          disabled={disabled}
          aria-label="Mention an AI employee, workflow, task, or memory"
          className="size-9 text-muted-foreground"
        >
          <AtSign className="size-4" aria-hidden="true" />
        </Button>
      )}
    />
  );
}
