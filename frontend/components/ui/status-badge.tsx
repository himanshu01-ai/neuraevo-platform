import { Badge, type BadgeProps } from "./badge";
import { cn } from "@/lib/utils";
import {
  APPROVAL_LABEL,
  APPROVAL_TONE,
  HEALTH_LABEL,
  HEALTH_TONE,
  LIFECYCLE_LABEL,
  LIFECYCLE_TONE,
  NODE_LABEL,
  NODE_TONE,
  WORKFLOW_LABEL,
  WORKFLOW_TONE,
  type ApprovalStatus,
  type HealthState,
  type LifecycleStatus,
  type NodeStatus,
  type StatusTone,
  type WorkflowStatus,
} from "@/types/domain";

/** Tone → Badge variant. `neutral` has no dedicated variant; it reads as default. */
export const TONE_VARIANT: Record<StatusTone, NonNullable<BadgeProps["variant"]>> = {
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info",
  neutral: "default",
};

/** Tone → dot color, for surfaces that show a bare indicator instead of a pill. */
export const TONE_DOT: Record<StatusTone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-destructive",
  info: "bg-info",
  neutral: "bg-muted-foreground",
};

/** One badge for every status vocabulary in `types/domain.ts`. */
export type StatusBadgeProps = { className?: string } & (
  | { kind: "lifecycle"; status: LifecycleStatus }
  | { kind: "approval"; status: ApprovalStatus }
  | { kind: "node"; status: NodeStatus }
  | { kind: "health"; status: HealthState }
  | { kind: "workflow"; status: WorkflowStatus }
);

function resolve(props: StatusBadgeProps): { label: string; tone: StatusTone; isLive: boolean } {
  switch (props.kind) {
    case "lifecycle":
      return {
        label: LIFECYCLE_LABEL[props.status],
        tone: LIFECYCLE_TONE[props.status],
        isLive: props.status === "RUNNING",
      };
    case "approval":
      return { label: APPROVAL_LABEL[props.status], tone: APPROVAL_TONE[props.status], isLive: false };
    case "node":
      return {
        label: NODE_LABEL[props.status],
        tone: NODE_TONE[props.status],
        isLive: props.status === "RUNNING",
      };
    case "health":
      return { label: HEALTH_LABEL[props.status], tone: HEALTH_TONE[props.status], isLive: false };
    case "workflow":
      return { label: WORKFLOW_LABEL[props.status], tone: WORKFLOW_TONE[props.status], isLive: false };
  }
}

/**
 * Resolves a backend status → tone → color through the `types/domain.ts` maps and
 * renders a dot plus a label, so status is never carried by color alone. A
 * RUNNING status breathes; the global reduced-motion rule stills it.
 */
export function StatusBadge(props: StatusBadgeProps) {
  const { label, tone, isLive } = resolve(props);

  return (
    <Badge variant={TONE_VARIANT[tone]} className={props.className}>
      <span
        aria-hidden="true"
        className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone], isLive && "animate-pulse-glow")}
      />
      {label}
    </Badge>
  );
}
