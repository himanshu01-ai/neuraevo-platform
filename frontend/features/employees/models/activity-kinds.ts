import {
  CircleCheck,
  Pause,
  Play,
  Plus,
  Settings2,
  SquarePen,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { ACTIVITY_KINDS, type ActivityKind } from "@/services/employees";
import type { StatusTone } from "@/types/domain";

/**
 * How each activity event reads on the timeline. Tone resolves through the same
 * `StatusTone` scale as every other coloured surface, so a completed event is
 * the same green as a COMPLETED status elsewhere.
 */

export interface ActivityMeta {
  kind: ActivityKind;
  label: string;
  icon: LucideIcon;
  tone: StatusTone;
}

export const ACTIVITY_META: Record<ActivityKind, ActivityMeta> = {
  CREATED: { kind: "CREATED", label: "Created", icon: Plus, tone: "info" },
  UPDATED: { kind: "UPDATED", label: "Updated", icon: SquarePen, tone: "neutral" },
  ASSIGNED: { kind: "ASSIGNED", label: "Assigned", icon: Workflow, tone: "info" },
  PAUSED: { kind: "PAUSED", label: "Paused", icon: Pause, tone: "warning" },
  RESUMED: { kind: "RESUMED", label: "Resumed", icon: Play, tone: "success" },
  COMPLETED: { kind: "COMPLETED", label: "Completed", icon: CircleCheck, tone: "success" },
  CONFIGURATION_CHANGED: {
    kind: "CONFIGURATION_CHANGED",
    label: "Configuration changed",
    icon: Settings2,
    tone: "neutral",
  },
};

/** Every activity kind in canonical order. */
export const ACTIVITY_LIST: readonly ActivityMeta[] = ACTIVITY_KINDS.map((kind) => ACTIVITY_META[kind]);
