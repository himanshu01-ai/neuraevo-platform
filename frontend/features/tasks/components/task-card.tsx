"use client";

import { memo } from "react";
import Link from "next/link";
import { Copy, Ellipsis, ListOrdered, SquareArrowOutUpRight } from "lucide-react";
import {
  ALLOWED_COMMANDS,
  TASK_EXECUTION_MODE_LABEL,
  type TaskCommand,
  type TaskSummary,
} from "@/services/tasks";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { Progress } from "@/components/ui/progress";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { TASK_COMMAND_META } from "../models/task-commands";
import { TaskStateBadge } from "./task-state-badge";
import { cn } from "@/lib/utils";

export interface TaskCardProps {
  task: TaskSummary;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
  onCommand: (id: string, command: TaskCommand) => void;
  onDuplicate: (id: string) => void;
}

/**
 * One task at a glance: what it is, what's running it, who's carrying it, and
 * how far along it is.
 *
 * The actions menu offers only what the task's state actually accepts — the list
 * comes from `ALLOWED_COMMANDS`, the same table the adapter refuses by, so a menu
 * item is never a button that will fail.
 *
 * The card body is a button, not a link: selecting a task fills the panels
 * beside it rather than navigating. The menu and the profile link sit outside
 * that button so their clicks aren't swallowed.
 */
export const TaskCard = memo(function TaskCard({
  task,
  isSelected = false,
  onSelect,
  onCommand,
  onDuplicate,
}: TaskCardProps) {
  const commands = ALLOWED_COMMANDS[task.state];

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-lg border bg-card p-4 shadow-sm transition-all",
        "hover:border-primary/30 hover:shadow-md",
        isSelected && "border-primary/50 ring-2 ring-primary/30"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-xs text-muted-foreground">{task.businessId}</p>
          <h3 className="mt-0.5 truncate text-sm font-semibold text-foreground">
            {onSelect ? (
              // Stretched over the card so the whole surface selects, while the
              // menu and the link stay clickable above it.
              <button
                type="button"
                onClick={() => onSelect(task.id)}
                aria-pressed={isSelected}
                className="rounded-sm text-left after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {task.name}
              </button>
            ) : (
              task.name
            )}
          </h3>
        </div>

        <div className="relative z-10 flex shrink-0 items-center gap-1.5">
          <TaskStateBadge state={task.state} />
          <DropdownMenu
            menuLabel={`Actions for ${task.name}`}
            align="end"
            items={[
              {
                key: "open",
                label: "Open task",
                icon: SquareArrowOutUpRight,
                href: `/workspace/tasks/${task.id}`,
              },
              { key: "duplicate", label: "Duplicate", icon: Copy, onSelect: () => onDuplicate(task.id) },
              ...commands.map((command) => ({
                key: command,
                label: TASK_COMMAND_META[command].label,
                icon: TASK_COMMAND_META[command].icon,
                destructive: TASK_COMMAND_META[command].destructive,
                onSelect: () => onCommand(task.id, command),
              })),
            ]}
            renderTrigger={(props) => (
              <Button
                {...props}
                variant="ghost"
                size="icon"
                className="size-7 text-muted-foreground"
                aria-label={`Actions for ${task.name}`}
              >
                <Ellipsis className="size-4" aria-hidden="true" />
              </Button>
            )}
          />
        </div>
      </div>

      <p className="mt-2 line-clamp-2 flex-1 text-sm text-muted-foreground">{task.description}</p>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Badge variant={TONE_VARIANT[PRIORITY_TONE[task.priority]]}>{PRIORITY_LABEL[task.priority]}</Badge>
        <Badge variant="outline">{TASK_EXECUTION_MODE_LABEL[task.executionMode]}</Badge>
        {task.queuePosition !== null ? (
          <Badge variant="default">
            <ListOrdered className="size-3 shrink-0" aria-hidden="true" />
            Queue #{task.queuePosition}
          </Badge>
        ) : null}
      </div>

      <div className="mt-3 space-y-2 border-t pt-3">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="min-w-0 truncate text-muted-foreground">
            <span className="sr-only">Workflow: </span>
            {task.workflow ? (
              <Link
                href={`/workspace/workflows/${task.workflow.workflowId}`}
                className="relative z-10 rounded-sm transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {task.workflow.workflowName}
              </Link>
            ) : (
              "No workflow assigned"
            )}
          </span>

          {task.assignee ? (
            <span className="flex shrink-0 items-center gap-1.5 text-muted-foreground">
              <Avatar name={task.assignee.employeeName} className="size-5 text-[0.625rem]" />
              <span className="sr-only">Assigned to: </span>
              {task.assignee.employeeName}
            </span>
          ) : (
            <span className="shrink-0 text-muted-foreground">Unassigned</span>
          )}
        </div>

        <div>
          <Progress value={task.progress} label={`${task.name} progress`} />
          <p className="mt-1 text-xs text-muted-foreground">{task.progress}% complete</p>
        </div>
      </div>
    </div>
  );
});
