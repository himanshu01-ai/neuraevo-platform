import { Archive, Import, Link2, Plus, ScanEye, SquarePen, type LucideIcon } from "lucide-react";
import { TIMELINE_EVENT_KINDS, type TimelineEventKind } from "@/services/memory";
import type { StatusTone } from "@/types/domain";

/**
 * How each event reads on the timeline. Tone resolves through the same
 * `StatusTone` scale as every other coloured surface, so a review flag is the
 * same amber as a warning elsewhere.
 */

export interface TimelineEventMeta {
  kind: TimelineEventKind;
  label: string;
  icon: LucideIcon;
  tone: StatusTone;
}

export const TIMELINE_EVENT_META: Record<TimelineEventKind, TimelineEventMeta> = {
  CREATED: { kind: "CREATED", label: "Created", icon: Plus, tone: "info" },
  UPDATED: { kind: "UPDATED", label: "Updated", icon: SquarePen, tone: "neutral" },
  LINKED: { kind: "LINKED", label: "Linked", icon: Link2, tone: "info" },
  IMPORTED: { kind: "IMPORTED", label: "Imported", icon: Import, tone: "success" },
  REVIEWED: { kind: "REVIEWED", label: "Reviewed", icon: ScanEye, tone: "warning" },
  ARCHIVED: { kind: "ARCHIVED", label: "Archived", icon: Archive, tone: "neutral" },
};

/** Every event kind in canonical order. */
export const TIMELINE_EVENT_LIST: readonly TimelineEventMeta[] = TIMELINE_EVENT_KINDS.map(
  (kind) => TIMELINE_EVENT_META[kind]
);
