import { Info } from "lucide-react";
import { UNSUPPORTED_MESSAGE } from "@/services/employees";
import { cn } from "@/lib/utils";

export interface BackendSupportNoticeProps {
  /** What specifically isn't stored yet, e.g. "Capability grants". */
  what: string;
  className?: string;
}

/**
 * Says plainly that a section can be seen but not saved yet.
 *
 * The employee backend stores only name, role, description, language and
 * behaviour, so several authoring sections have nowhere to persist to. They
 * stay visible — the functionality is coming, and hiding it would misrepresent
 * the product — but they are disabled and labelled, so nothing a user types is
 * silently discarded.
 *
 * Announced politely: it's context for the section, not an error to interrupt
 * with.
 */
export function BackendSupportNotice({ what, className }: BackendSupportNoticeProps) {
  return (
    <p
      role="note"
      className={cn(
        "flex items-start gap-2 rounded-md border border-border bg-muted/40 p-2.5 text-xs text-muted-foreground",
        className
      )}
    >
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      <span>
        {what} {UNSUPPORTED_MESSAGE} You can review the options here, but they won&apos;t be
        saved yet.
      </span>
    </p>
  );
}

