"use client";

import { ArrowDownUp, Bot, Copy, LayoutGrid, List, Plus, Search, Workflow, X } from "lucide-react";
import {
  ALLOWED_COMMANDS,
  TASK_EXECUTION_MODES,
  TASK_EXECUTION_MODE_LABEL,
  type TaskCommand,
  type TaskDetail,
  type TaskExecutionMode,
  type TaskState,
} from "@/services/tasks";
import type { Priority } from "@/types/domain";
import {
  TASK_SORTS,
  TASK_SORT_LABEL,
  hasActiveTaskFilters,
  useTaskStore,
  type TaskSort,
  type TaskViewMode,
} from "@/store/tasks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useEmployeeOptions, useWorkflowOptions } from "../hooks/use-assignment-options";
import { priorityOptions, stateOptions } from "../hooks/use-filtered-tasks";
import { TASK_COMMAND_LIST } from "../models/task-commands";
import { cn } from "@/lib/utils";

const VIEW_MODES: { mode: TaskViewMode; label: string; icon: typeof LayoutGrid }[] = [
  { mode: "grid", label: "Cards", icon: LayoutGrid },
  { mode: "list", label: "Compact", icon: List },
];

export interface TaskToolbarProps {
  /** The task the commands act on. `null` disables everything task-specific. */
  task: TaskDetail | null;
  onCommand: (command: TaskCommand) => void;
  onDuplicate: () => void;
  onAssignWorkflow: (workflowId: string) => void;
  onAssignEmployee: (employeeId: string) => void;
  isBusy?: boolean;
}

/**
 * Everything you can do to the board, and to the task you've selected.
 *
 * Commands enable from `ALLOWED_COMMANDS` — the same table the adapter refuses
 * by — so a button is offered only when the task's state would actually accept
 * it. A disabled Resume on a running task is the rule showing through, not a
 * guess made here.
 *
 * Nothing on this toolbar executes anything: each control asks the platform for
 * a change and reports what it says back.
 */
export function TaskToolbar({
  task,
  onCommand,
  onDuplicate,
  onAssignWorkflow,
  onAssignEmployee,
  isBusy = false,
}: TaskToolbarProps) {
  const filters = useTaskStore((s) => s.filters);
  const sort = useTaskStore((s) => s.sort);
  const viewMode = useTaskStore((s) => s.viewMode);
  const setSearch = useTaskStore((s) => s.setSearch);
  const setStateFilter = useTaskStore((s) => s.setStateFilter);
  const setPriorityFilter = useTaskStore((s) => s.setPriorityFilter);
  const setExecutionModeFilter = useTaskStore((s) => s.setExecutionModeFilter);
  const resetFilters = useTaskStore((s) => s.resetFilters);
  const setSort = useTaskStore((s) => s.setSort);
  const setViewMode = useTaskStore((s) => s.setViewMode);

  // Real workflows and employees to assign, from the same caches their own
  // workspaces read (Sprint 19).
  const workflowOptions = useWorkflowOptions();
  const employeeOptions = useEmployeeOptions();

  const allowed = task ? ALLOWED_COMMANDS[task.state] : [];
  const isFiltered = hasActiveTaskFilters(filters);

  return (
    <div className="space-y-3 rounded-lg border bg-card p-3 shadow-sm">
      {/* Row 1 — what you can do */}
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" href="/workspace/tasks/new">
          <Plus className="size-4" aria-hidden="true" />
          Create task
        </Button>

        <Button variant="outline" size="sm" onClick={onDuplicate} disabled={!task || isBusy}>
          <Copy className="size-4" aria-hidden="true" />
          Duplicate
        </Button>

        <span aria-hidden="true" className="mx-1 hidden h-5 w-px bg-border sm:block" />

        <label className="sr-only" htmlFor="assign-workflow">
          Assign workflow
        </label>
        <Select
          id="assign-workflow"
          value={task?.workflow?.workflowId ?? ""}
          onChange={(event) => onAssignWorkflow(event.target.value)}
          disabled={!task || isBusy}
          className="h-8 w-auto min-w-40 text-xs"
        >
          <option value="" disabled>
            Assign workflow…
          </option>
          {(workflowOptions.data ?? []).map((option) => (
            <option key={option.id} value={option.id}>
              {option.name}
            </option>
          ))}
        </Select>

        <label className="sr-only" htmlFor="assign-employee">
          Assign employee
        </label>
        <Select
          id="assign-employee"
          value={task?.assignee?.employeeId ?? ""}
          onChange={(event) => onAssignEmployee(event.target.value)}
          disabled={!task || isBusy}
          className="h-8 w-auto min-w-36 text-xs"
        >
          <option value="" disabled>
            Assign employee…
          </option>
          {(employeeOptions.data ?? []).map((option) => (
            <option key={option.id} value={option.id}>
              {option.name}
            </option>
          ))}
        </Select>

        <span aria-hidden="true" className="mx-1 hidden h-5 w-px bg-border sm:block" />

        {TASK_COMMAND_LIST.map(({ command, label, icon: Icon, destructive }) => (
          <Button
            key={command}
            variant={destructive ? "ghost" : "outline"}
            size="sm"
            disabled={!task || isBusy || !allowed.includes(command)}
            onClick={() => onCommand(command)}
            className={cn(destructive && "text-destructive hover:bg-destructive/10")}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </Button>
        ))}
      </div>

      {/* Row 2 — what you're looking at */}
      <div className="flex flex-wrap items-center gap-2 border-t pt-3">
        <div className="relative min-w-48 flex-1 sm:max-w-64">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            value={filters.search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search tasks"
            aria-label="Search tasks"
            className="h-8 pl-9 text-xs"
          />
        </div>

        <Select
          value={filters.state}
          onChange={(event) => setStateFilter(event.target.value as TaskState | "ALL")}
          aria-label="Filter by state"
          className="h-8 w-auto min-w-28 text-xs"
        >
          <option value="ALL">Any state</option>
          {stateOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>

        <Select
          value={filters.priority}
          onChange={(event) => setPriorityFilter(event.target.value as Priority | "ALL")}
          aria-label="Filter by priority"
          className="h-8 w-auto min-w-28 text-xs"
        >
          <option value="ALL">Any priority</option>
          {priorityOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>

        <Select
          value={filters.executionMode}
          onChange={(event) => setExecutionModeFilter(event.target.value as TaskExecutionMode | "ALL")}
          aria-label="Filter by execution mode"
          className="h-8 w-auto min-w-32 text-xs"
        >
          <option value="ALL">Any mode</option>
          {TASK_EXECUTION_MODES.map((mode) => (
            <option key={mode} value={mode}>
              {TASK_EXECUTION_MODE_LABEL[mode]}
            </option>
          ))}
        </Select>

        <span className="inline-flex items-center gap-1.5">
          <ArrowDownUp className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <Select
            value={sort}
            onChange={(event) => setSort(event.target.value as TaskSort)}
            aria-label="Sort tasks"
            className="h-8 w-auto min-w-28 text-xs"
          >
            {TASK_SORTS.map((value) => (
              <option key={value} value={value}>
                {TASK_SORT_LABEL[value]}
              </option>
            ))}
          </Select>
        </span>

        {isFiltered ? (
          <Button variant="ghost" size="sm" className="h-8" onClick={resetFilters}>
            <X className="size-4" aria-hidden="true" />
            Clear
          </Button>
        ) : null}

        <div
          role="group"
          aria-label="View mode"
          className="ml-auto flex shrink-0 items-center gap-0.5 rounded-md border bg-background p-0.5"
        >
          {VIEW_MODES.map(({ mode, label, icon: Icon }) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              aria-pressed={viewMode === mode}
              className={cn(
                "inline-flex size-7 items-center justify-center rounded-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                viewMode === mode
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              <span className="sr-only">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Quick links to the screens that manage the board as a whole. */}
      <div className="flex flex-wrap items-center gap-2 border-t pt-3">
        <Button variant="ghost" size="sm" href="/workspace/tasks/queue">
          <List className="size-4" aria-hidden="true" />
          Queue manager
        </Button>
        <Button variant="ghost" size="sm" href="/workspace/tasks/approvals">
          <Workflow className="size-4" aria-hidden="true" />
          Approvals
        </Button>
        <Button variant="ghost" size="sm" href="/workspace/tasks/history">
          <Bot className="size-4" aria-hidden="true" />
          History
        </Button>
      </div>
    </div>
  );
}
