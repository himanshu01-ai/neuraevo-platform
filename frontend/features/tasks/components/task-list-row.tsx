"use client";

import { memo } from "react";
import { motion } from "framer-motion";
import type { TaskSummary } from "@/services/tasks";
import { Progress } from "@/components/ui/progress";
import { TaskStateBadge } from "./task-state-badge";
import { cn } from "@/lib/utils";

export interface TaskListRowProps {
  task: TaskSummary;
  isSelected: boolean;
  onSelect: (id: string) => void;
}

/**
 * One task, compactly — the queue column's dense mode. Says what it is, where it
 * stands, and how far along; the card says the rest.
 *
 * The selection marker is one shared element (`layoutId`) rather than one per
 * row, so it slides from the old selection to the new instead of blinking.
 * Reduced motion collapses that to a cut via the global MotionConfig.
 */
export const TaskListRow = memo(function TaskListRow({ task, isSelected, onSelect }: TaskListRowProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(task.id)}
      aria-pressed={isSelected}
      className={cn(
        "relative flex w-full flex-col gap-1.5 overflow-hidden rounded-md border px-3 py-2.5 text-left transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isSelected ? "border-primary/40 bg-primary/5" : "border-transparent hover:bg-accent"
      )}
    >
      {isSelected ? (
        <motion.span
          layoutId="task-selection"
          aria-hidden="true"
          className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary"
          transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        />
      ) : null}

      <span className="flex items-start justify-between gap-2">
        <span className="min-w-0">
          <span className="block font-mono text-[0.6875rem] text-muted-foreground">{task.businessId}</span>
          <span className="block truncate text-sm font-medium text-foreground">{task.name}</span>
        </span>
        <TaskStateBadge state={task.state} className="shrink-0" />
      </span>

      <span className="flex items-center gap-2">
        <Progress value={task.progress} label={`${task.name} progress`} className="h-1 flex-1" />
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{task.progress}%</span>
      </span>
    </button>
  );
});
