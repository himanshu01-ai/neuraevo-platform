"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { MousePointerSquareDashed } from "lucide-react";
import type { TaskCommand } from "@/services/tasks";
import { useTaskStore } from "@/store/tasks";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Reveal } from "@/components/motion/reveal";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import {
  useAssignEmployee,
  useAssignWorkflow,
  useDuplicateTask,
  useTaskCommand,
  useTaskDetail,
  useTaskList,
} from "../hooks/use-tasks";
import { useFilteredTasks } from "../hooks/use-filtered-tasks";
import { TASK_COMMAND_META } from "../models/task-commands";
import { TaskEmptyState } from "./task-empty-state";
import { TaskList } from "./task-list";
import { TaskToolbar } from "./task-toolbar";
import {
  ExecutionGraphLoading,
  TaskCardListLoading,
  TaskInspectorLoading,
  TaskListLoading,
} from "./task-loading-state";

/**
 * Mission control: the board on the left, the selected task's run in the middle,
 * what it's doing on the right, and its record below.
 *
 * The graph and the inspector are the heavy half of this screen and neither is
 * needed to render the board, so both load on demand — the list paints first and
 * the panels arrive with their own placeholders.
 *
 * Below `xl` the three columns stack in reading order (board, run, inspector,
 * dock) rather than switching on a media query: a layout that only depends on
 * CSS can't disagree with the server about what to render on first paint.
 *
 * Nothing on this screen executes anything. Commands ask the platform for a
 * change; the platform is what would carry it out.
 */

const ExecutionGraph = dynamic(() => import("../execution/execution-graph").then((m) => m.ExecutionGraph), {
  loading: () => <ExecutionGraphLoading />,
});

const TaskInspector = dynamic(() => import("./task-inspector").then((m) => m.TaskInspector), {
  loading: () => <TaskInspectorLoading />,
});

const TaskDock = dynamic(() => import("./task-dock").then((m) => m.TaskDock), {
  loading: () => <div className="h-64 rounded-lg border bg-card shadow-sm" />,
});

export function TaskDirectory() {
  const query = useTaskList();
  const filters = useTaskStore((s) => s.filters);
  const sort = useTaskStore((s) => s.sort);
  const viewMode = useTaskStore((s) => s.viewMode);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const selectTask = useTaskStore((s) => s.selectTask);

  const detail = useTaskDetail(selectedTaskId);
  const command = useTaskCommand();
  const duplicate = useDuplicateTask();
  const assignWorkflow = useAssignWorkflow();
  const assignEmployee = useAssignEmployee();

  const [notice, setNotice] = useState<{ tone: "info" | "error"; message: string } | null>(null);

  const tasks = useFilteredTasks(query.data, filters, sort);

  // A selection outlives the board it came from: a task deleted in another tab
  // would otherwise leave the panels pointing at nothing.
  useEffect(() => {
    if (!query.data || selectedTaskId === null) return;
    if (!query.data.some((task) => task.id === selectedTaskId)) selectTask(null);
  }, [query.data, selectedTaskId, selectTask]);

  const runCommand = useCallback(
    (id: string, next: TaskCommand) => {
      setNotice(null);
      command.mutate(
        { id, command: next },
        {
          onSuccess: () => setNotice({ tone: "info", message: TASK_COMMAND_META[next].confirmation }),
          // The adapter refuses what the state forbids; say what it said rather
          // than pretending the click worked.
          onError: (error) =>
            setNotice({
              tone: "error",
              message: error instanceof Error ? error.message : "That couldn't be done.",
            }),
        }
      );
    },
    [command]
  );

  const handleDuplicate = useCallback(
    (id: string) => {
      setNotice(null);
      duplicate.mutate(id, {
        onSuccess: (clone) => {
          selectTask(clone.id);
          setNotice({ tone: "info", message: `Copied to ${clone.businessId}.` });
        },
      });
    },
    [duplicate, selectTask]
  );

  const board = () => {
    if (query.isError) {
      return (
        <ErrorState
          title="Couldn't load tasks"
          description="Your tasks couldn't be loaded. Try again in a moment."
          onRetry={() => void query.refetch()}
        />
      );
    }

    if (query.isPending) return viewMode === "grid" ? <TaskCardListLoading /> : <TaskListLoading />;
    if (query.data.length === 0) return <TaskEmptyState />;

    if (tasks.length === 0) {
      return (
        <TaskEmptyState
          compact
          title="No tasks match"
          description="Try a different word, or clear the filters."
          showActions={false}
        />
      );
    }

    return (
      <TaskList tasks={tasks} viewMode={viewMode} onCommand={runCommand} onDuplicate={handleDuplicate} />
    );
  };

  const isBusy =
    command.isPending || duplicate.isPending || assignWorkflow.isPending || assignEmployee.isPending;

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkspaceHeader
          title="Tasks"
          description="Describe the work, watch it run, and step in when it needs you."
        />
      </Reveal>

      <div className="mt-6">
        <TaskToolbar
          task={detail.data ?? null}
          isBusy={isBusy}
          onCommand={(next) => selectedTaskId && runCommand(selectedTaskId, next)}
          onDuplicate={() => selectedTaskId && handleDuplicate(selectedTaskId)}
          onAssignWorkflow={(workflowId) =>
            selectedTaskId && assignWorkflow.mutate({ id: selectedTaskId, workflowId })
          }
          onAssignEmployee={(employeeId) =>
            selectedTaskId && assignEmployee.mutate({ id: selectedTaskId, employeeId })
          }
        />
      </div>

      {notice ? (
        <Alert variant={notice.tone === "error" ? "error" : "info"} className="mt-3">
          {notice.message}
        </Alert>
      ) : null}

      <div className="mt-4 flex flex-col gap-4 xl:flex-row">
        <div className="min-w-0 xl:w-80 xl:shrink-0">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Task queue
          </h2>
          {board()}
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Execution graph
          </h2>
          {detail.data ? (
            <ExecutionGraph
              graph={detail.data.graph}
              monitor={detail.data.monitor}
              taskId={detail.data.id}
              className="h-[28rem]"
            />
          ) : detail.isPending && selectedTaskId ? (
            <ExecutionGraphLoading className="h-[28rem]" />
          ) : (
            <div className="flex h-[28rem] items-center justify-center rounded-lg border bg-card">
              <EmptyState
                icon={MousePointerSquareDashed}
                title="No task selected"
                description="Pick a task to see how its run is wired."
              />
            </div>
          )}
        </div>

        <div className="min-w-0 xl:w-80 xl:shrink-0">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Inspector
          </h2>
          <section
            aria-label="Task inspector"
            className="rounded-lg border bg-card p-4 shadow-sm xl:max-h-[28rem] xl:overflow-y-auto"
          >
            {detail.data ? (
              <TaskInspector task={detail.data} />
            ) : detail.isPending && selectedTaskId ? (
              <TaskInspectorLoading />
            ) : (
              <EmptyState
                compact
                icon={MousePointerSquareDashed}
                title="Nothing selected"
                description="Pick a task, then a node."
              />
            )}
          </section>
        </div>
      </div>

      <div className="mt-4">
        <TaskDock task={detail.data ?? null} />
      </div>
    </WorkspaceContent>
  );
}
