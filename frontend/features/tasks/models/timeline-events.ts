import {
  Bell,
  Brain,
  CircleCheck,
  ListPlus,
  Route,
  ShieldCheck,
  ShieldQuestion,
  Timer,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { TIMELINE_EVENT_KINDS, type TimelineEventKind } from "@/services/tasks";
import type { StatusTone } from "@/types/domain";

/**
 * How each milestone reads on the timeline. Tone resolves through the same
 * `StatusTone` scale as every other coloured surface, so a completed event is
 * the same green as a COMPLETED state elsewhere.
 */

export interface TimelineEventMeta {
  kind: TimelineEventKind;
  label: string;
  icon: LucideIcon;
  tone: StatusTone;
}

export const TIMELINE_EVENT_META: Record<TimelineEventKind, TimelineEventMeta> = {
  TASK_CREATED: { kind: "TASK_CREATED", label: "Task created", icon: ListPlus, tone: "info" },
  QUEUED: { kind: "QUEUED", label: "Queued", icon: Timer, tone: "info" },
  PLANNING_STARTED: { kind: "PLANNING_STARTED", label: "Planning started", icon: Route, tone: "info" },
  WORKFLOW_STARTED: { kind: "WORKFLOW_STARTED", label: "Workflow started", icon: Workflow, tone: "info" },
  CAPABILITY_INVOKED: { kind: "CAPABILITY_INVOKED", label: "Capability invoked", icon: Wrench, tone: "neutral" },
  APPROVAL_REQUESTED: {
    kind: "APPROVAL_REQUESTED",
    label: "Approval requested",
    icon: ShieldQuestion,
    tone: "warning",
  },
  APPROVAL_COMPLETED: {
    kind: "APPROVAL_COMPLETED",
    label: "Approval completed",
    icon: ShieldCheck,
    tone: "success",
  },
  MEMORY_UPDATED: { kind: "MEMORY_UPDATED", label: "Memory updated", icon: Brain, tone: "neutral" },
  NOTIFICATION_SENT: { kind: "NOTIFICATION_SENT", label: "Notification sent", icon: Bell, tone: "neutral" },
  TASK_COMPLETED: { kind: "TASK_COMPLETED", label: "Task completed", icon: CircleCheck, tone: "success" },
};

/** Every milestone in canonical order. */
export const TIMELINE_EVENT_LIST: readonly TimelineEventMeta[] = TIMELINE_EVENT_KINDS.map(
  (kind) => TIMELINE_EVENT_META[kind]
);
