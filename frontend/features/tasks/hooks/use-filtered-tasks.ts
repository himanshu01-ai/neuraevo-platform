"use client";

import { useMemo } from "react";
import { TASK_STATES, TASK_STATE_LABEL, type TaskSummary } from "@/services/tasks";
import type { TaskFilters, TaskSort } from "@/store/tasks";
import { PRIORITY_LABEL, type Priority } from "@/types/domain";

/**
 * The board narrowed by the toolbar's filters and put in the chosen order.
 *
 * Filtering and sorting are derived, never stored: the store holds the question,
 * the Query cache holds the board, and this recomputes the answer. Nothing to
 * keep in sync, so nothing can drift.
 *
 * Search matches the name, the description, and the business id — someone
 * hunting "TSK-1042" is quoting the id they can see, and someone typing
 * "pricing" means the words.
 */

/** Most urgent first. */
const PRIORITY_RANK: Record<Priority, number> = { URGENT: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

/** Board order: the shape of a task's life, matching the filter legend. */
const STATE_RANK: Record<string, number> = Object.fromEntries(
  TASK_STATES.map((state, index) => [state, index])
);

export function useFilteredTasks(
  tasks: readonly TaskSummary[] | undefined,
  filters: TaskFilters,
  sort: TaskSort
): TaskSummary[] {
  return useMemo(() => {
    const rows = tasks ?? [];
    const term = filters.search.trim().toLowerCase();

    const matched = rows.filter((task) => {
      if (filters.state !== "ALL" && task.state !== filters.state) return false;
      if (filters.priority !== "ALL" && task.priority !== filters.priority) return false;
      if (filters.executionMode !== "ALL" && task.executionMode !== filters.executionMode) return false;
      if (!term) return true;

      const haystack = [task.name, task.description, task.businessId].join(" ").toLowerCase();
      return haystack.includes(term);
    });

    // `list` is already in the platform's sequence order, so `recent` leaves it
    // alone rather than re-deriving what the platform already decided.
    if (sort === "recent") return matched;

    const ordered = matched.slice();
    switch (sort) {
      case "priority":
        ordered.sort((a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]);
        break;
      case "state":
        ordered.sort((a, b) => (STATE_RANK[a.state] ?? 0) - (STATE_RANK[b.state] ?? 0));
        break;
      case "progress":
        ordered.sort((a, b) => b.progress - a.progress);
        break;
    }
    return ordered;
  }, [tasks, filters, sort]);
}

/** Labels for the filter selects, kept beside the ordering they belong to. */
export const stateOptions = TASK_STATES.map((state) => ({ value: state, label: TASK_STATE_LABEL[state] }));

export const priorityOptions = (["LOW", "MEDIUM", "HIGH", "URGENT"] as const).map((priority) => ({
  value: priority,
  label: PRIORITY_LABEL[priority],
}));
