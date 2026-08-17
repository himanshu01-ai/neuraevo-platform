"use client";

import { useCallback } from "react";
import { motion } from "framer-motion";
import type { TaskCommand, TaskSummary } from "@/services/tasks";
import { useTaskStore, type TaskViewMode } from "@/store/tasks";
import { TaskCard } from "./task-card";
import { TaskListRow } from "./task-list-row";
import { cn } from "@/lib/utils";

export interface TaskListProps {
  tasks: readonly TaskSummary[];
  viewMode: TaskViewMode;
  onCommand: (id: string, command: TaskCommand) => void;
  onDuplicate: (id: string) => void;
  className?: string;
}

/**
 * The directory's task column.
 *
 * Both modes render the same tasks, differing only in how much they say: cards
 * are roomy, rows are dense. Handlers are `useCallback`-stable and the items are
 * memoized, so filtering or selecting re-renders the one item that changed
 * rather than the whole list.
 *
 * Rows animate in but not out. <AnimatePresence> would be the usual way to get
 * an exit, but framer-motion 11 and React 19 disagree about it badly enough that
 * filtered-out rows stay mounted (found and fixed the same way in Sprint 17.6) —
 * a wrong list is a worse outcome than a missing flourish.
 */
export function TaskList({ tasks, viewMode, onCommand, onDuplicate, className }: TaskListProps) {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const selectTask = useTaskStore((s) => s.selectTask);

  const handleSelect = useCallback((id: string) => selectTask(id), [selectTask]);

  return (
    <ul className={cn(viewMode === "grid" ? "space-y-3" : "space-y-1", className)}>
      {tasks.map((task) => (
        <motion.li
          key={task.id}
          layout="position"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          {viewMode === "grid" ? (
            <TaskCard
              task={task}
              isSelected={selectedTaskId === task.id}
              onSelect={handleSelect}
              onCommand={onCommand}
              onDuplicate={onDuplicate}
            />
          ) : (
            <TaskListRow task={task} isSelected={selectedTaskId === task.id} onSelect={handleSelect} />
          )}
        </motion.li>
      ))}
    </ul>
  );
}
