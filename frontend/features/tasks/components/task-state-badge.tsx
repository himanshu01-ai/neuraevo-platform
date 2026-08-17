import { Badge } from "@/components/ui/badge";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { TASK_STATE_LABEL, TASK_STATE_TONE, isLive, type TaskState } from "@/services/tasks";
import { cn } from "@/lib/utils";

export interface TaskStateBadgeProps {
  state: TaskState;
  className?: string;
}

/**
 * A task's state as a dot plus a label, so state is never carried by colour
 * alone. A live state breathes the way RUNNING does elsewhere; the global
 * reduced-motion rule stills it.
 *
 * This composes <Badge> with the tone tables `StatusBadge` exports rather than
 * extending `StatusBadge` itself: that primitive resolves the vocabularies in
 * `types/domain.ts`, and three of the ten task states have no backend
 * counterpart to mirror (see `services/tasks/types.ts`). Same primitive, same
 * tones, same pixels.
 */
export function TaskStateBadge({ state, className }: TaskStateBadgeProps) {
  const tone = TASK_STATE_TONE[state];

  return (
    <Badge variant={TONE_VARIANT[tone]} className={className}>
      <span
        aria-hidden="true"
        className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone], isLive(state) && "animate-pulse-glow")}
      />
      {TASK_STATE_LABEL[state]}
    </Badge>
  );
}
