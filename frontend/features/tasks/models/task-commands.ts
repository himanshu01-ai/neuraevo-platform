import {
  Ban,
  Bot,
  CalendarClock,
  Hand,
  ListPlus,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import {
  TASK_COMMANDS,
  TASK_EXECUTION_MODES,
  type TaskCommand,
  type TaskExecutionMode,
} from "@/services/tasks";

/**
 * How each toolbar command reads, and what it means. Which commands are *legal*
 * is not decided here — that's `ALLOWED_COMMANDS` in `services/tasks`, so the
 * button and the adapter can't disagree.
 */

export interface TaskCommandMeta {
  command: TaskCommand;
  label: string;
  icon: LucideIcon;
  /** Said back to the user once the request lands. */
  confirmation: string;
  destructive: boolean;
}

export const TASK_COMMAND_META: Record<TaskCommand, TaskCommandMeta> = {
  queue: {
    command: "queue",
    label: "Queue",
    icon: ListPlus,
    confirmation: "Queued. The platform starts it when it reaches the front.",
    destructive: false,
  },
  pause: {
    command: "pause",
    label: "Pause",
    icon: Pause,
    confirmation: "Paused. Nothing new will start until you resume it.",
    destructive: false,
  },
  resume: {
    command: "resume",
    label: "Resume",
    icon: Play,
    confirmation: "Resumed. The platform picks it back up from where it stopped.",
    destructive: false,
  },
  cancel: {
    command: "cancel",
    label: "Cancel",
    icon: Ban,
    confirmation: "Cancelled. Nothing further will run.",
    destructive: true,
  },
  retry: {
    command: "retry",
    label: "Retry",
    icon: RotateCcw,
    confirmation: "Queued to run again from the start.",
    destructive: false,
  },
};

/** Every command in canonical toolbar order. */
export const TASK_COMMAND_LIST: readonly TaskCommandMeta[] = TASK_COMMANDS.map(
  (command) => TASK_COMMAND_META[command]
);

/** How each execution mode reads. */
export interface ExecutionModeMeta {
  mode: TaskExecutionMode;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const EXECUTION_MODE_META: Record<TaskExecutionMode, ExecutionModeMeta> = {
  AUTOMATIC: {
    mode: "AUTOMATIC",
    label: "Automatic",
    description: "Runs on its own once it reaches the front of the queue.",
    icon: Bot,
  },
  MANUAL: {
    mode: "MANUAL",
    label: "Manual",
    description: "Waits for you to start it.",
    icon: Hand,
  },
  APPROVAL_REQUIRED: {
    mode: "APPROVAL_REQUIRED",
    label: "Approval required",
    description: "Stops for a sign-off before anything leaves the platform.",
    icon: ShieldCheck,
  },
  SCHEDULED: {
    mode: "SCHEDULED",
    label: "Scheduled",
    description: "Runs on a schedule the platform keeps.",
    icon: CalendarClock,
  },
};

export const EXECUTION_MODE_LIST: readonly ExecutionModeMeta[] = TASK_EXECUTION_MODES.map(
  (mode) => EXECUTION_MODE_META[mode]
);
