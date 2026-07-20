"use client";

import { useState } from "react";
import { ArrowLeft, Copy, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ALLOWED_COMMANDS, TASK_EXECUTION_MODE_LABEL, type TaskCommand } from "@/services/tasks";
import { PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Reveal } from "@/components/motion/reveal";
import { ApprovalList } from "../approvals/approval-list";
import { ArtifactList } from "../artifacts/artifact-list";
import { ExecutionGraph } from "../execution/execution-graph";
import { ExecutionMonitor } from "../monitoring/execution-monitor";
import { ExecutionTimeline } from "../timeline/execution-timeline";
import { useDuplicateTask, useExecuteTask, useTaskCommand, useTaskDetail } from "../hooks/use-tasks";
import { TASK_COMMAND_META } from "../models/task-commands";
import { ResultsPanel } from "./results-panel";
import { TaskRunHistory } from "./task-run-history";
import { TaskInspectorLoading } from "./task-loading-state";
import { TaskStateBadge } from "./task-state-badge";
import { cn } from "@/lib/utils";

/**
 * One task in full: the run drawn, what the platform says about it, and
 * everything it produced — on a single page.
 *
 * The directory splits these across three columns and a dock; here they're
 * together, because this page exists for the moment you want the whole picture
 * of one task. Read-only apart from the commands, which ask the platform for a
 * change rather than making one.
 */
export function TaskDetails({ id }: { id: string }) {
  const router = useRouter();
  const query = useTaskDetail(id);
  const command = useTaskCommand();
  const duplicate = useDuplicateTask();
  const execute = useExecuteTask();
  const [notice, setNotice] = useState<{ tone: "info" | "error"; message: string } | null>(null);

  if (query.isPending) {
    return (
      <WorkspaceContent>
        <TaskInspectorLoading />
      </WorkspaceContent>
    );
  }

  if (query.isError || !query.data) {
    return (
      <WorkspaceContent>
        <ErrorState
          title="Task not found"
          description="This task doesn't exist, or it was deleted."
          action={
            <Button variant="outline" href="/workspace/tasks">
              Back to tasks
            </Button>
          }
        />
      </WorkspaceContent>
    );
  }

  const task = query.data;
  const allowed = ALLOWED_COMMANDS[task.state];
  // A launch makes sense while the task is live work; anything paused, waiting
  // or finished goes through its own control first. The backend enforces the
  // same rule — this only decides when the button is worth offering.
  const canRun =
    task.workflow !== null &&
    ["PENDING", "QUEUED", "PLANNING", "RUNNING"].includes(task.state);

  const runWorkflow = () => {
    setNotice(null);
    execute.mutate(task.id, {
      onSuccess: (updated) =>
        setNotice(
          updated.state === "COMPLETED"
            ? { tone: "info", message: "The workflow ran to completion." }
            : { tone: "error", message: "The workflow ran but did not complete — see the run history." }
        ),
      onError: (error) =>
        setNotice({
          tone: "error",
          message: error instanceof Error ? error.message : "That task couldn't be run.",
        }),
    });
  };

  const runCommand = (next: TaskCommand) => {
    setNotice(null);
    command.mutate(
      { id: task.id, command: next },
      {
        onSuccess: () => setNotice({ tone: "info", message: TASK_COMMAND_META[next].confirmation }),
        onError: (error) =>
          setNotice({
            tone: "error",
            message: error instanceof Error ? error.message : "That couldn't be done.",
          }),
      }
    );
  };

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkspaceHeader
          title={
            <span className="flex min-w-0 items-center gap-3">
              <span className="truncate">{task.name}</span>
              <TaskStateBadge state={task.state} />
            </span>
          }
          description={task.description}
          actions={
            <>
              <Button variant="ghost" size="icon" href="/workspace/tasks" aria-label="Back to tasks">
                <ArrowLeft className="size-4" aria-hidden="true" />
              </Button>
              <Button
                variant="outline"
                disabled={duplicate.isPending}
                onClick={() =>
                  duplicate.mutate(task.id, {
                    onSuccess: (clone) => router.push(`/workspace/tasks/${clone.id}`),
                  })
                }
              >
                <Copy className="size-4" aria-hidden="true" />
                {duplicate.isPending ? "Duplicating…" : "Duplicate"}
              </Button>
              {canRun ? (
                <Button disabled={execute.isPending} onClick={runWorkflow}>
                  <Play className="size-4" aria-hidden="true" />
                  {execute.isPending ? "Running…" : "Run workflow"}
                </Button>
              ) : null}
              {allowed.map((next) => {
                const meta = TASK_COMMAND_META[next];
                const Icon = meta.icon;
                return (
                  <Button
                    key={next}
                    variant={meta.destructive ? "ghost" : "outline"}
                    disabled={command.isPending}
                    onClick={() => runCommand(next)}
                    className={cn(meta.destructive && "text-destructive hover:bg-destructive/10")}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                    {meta.label}
                  </Button>
                );
              })}
            </>
          }
        />
      </Reveal>

      {notice ? (
        <Alert variant={notice.tone === "error" ? "error" : "info"} className="mt-4">
          {notice.message}
        </Alert>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-card px-4 py-3 text-xs shadow-sm">
        <span className="font-mono text-muted-foreground">{task.businessId}</span>
        <Badge variant={TONE_VARIANT[PRIORITY_TONE[task.priority]]}>{PRIORITY_LABEL[task.priority]}</Badge>
        <Badge variant="outline">{TASK_EXECUTION_MODE_LABEL[task.executionMode]}</Badge>

        <span className="text-muted-foreground">
          <span className="sr-only">Workflow: </span>
          {task.workflow ? (
            <Link
              href={`/workspace/workflows/${task.workflow.workflowId}`}
              className="rounded-sm transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {task.workflow.workflowName}
            </Link>
          ) : (
            "No workflow assigned"
          )}
        </span>

        {task.assignee ? (
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <Avatar name={task.assignee.employeeName} className="size-4 text-[0.5rem]" />
            <Link
              href={`/workspace/employees/${task.assignee.employeeId}`}
              className="rounded-sm transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {task.assignee.employeeName}
            </Link>
          </span>
        ) : (
          <span className="text-muted-foreground">Unassigned</span>
        )}

        {task.queuePosition !== null ? (
          <Badge variant="default">Queue #{task.queuePosition}</Badge>
        ) : null}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <Reveal>
            <Panel
              title="Execution graph"
              description="What the run is made of, and the path it took."
              bodyClassName="p-0"
            >
              <ExecutionGraph
                graph={task.graph}
                monitor={task.monitor}
                taskId={task.id}
                className="h-[26rem] rounded-none border-0"
              />
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel title="Artifacts" description="What this run produced.">
              <ArtifactList taskId={task.id} />
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel title="Approvals" description="Decisions this run asked a person for.">
              <ApprovalList taskId={task.id} />
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel title="Results" description="What the run came back with.">
              <ResultsPanel task={task} />
            </Panel>
          </Reveal>
        </div>

        <div className="min-w-0 space-y-6">
          <Reveal delay={0.05}>
            <Panel title="Monitor" description="What the platform reports.">
              <ExecutionMonitor monitor={task.monitor} graph={task.graph} />
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel title="Run history" description="Every run this task launched.">
              <TaskRunHistory
                taskId={task.id}
                onRetried={(message, tone) => setNotice({ tone, message })}
              />
            </Panel>
          </Reveal>

          <Reveal delay={0.1}>
            <Panel title="Timeline" description="Newest first.">
              <ExecutionTimeline taskId={task.id} graph={task.graph} />
            </Panel>
          </Reveal>
        </div>
      </div>
    </WorkspaceContent>
  );
}
