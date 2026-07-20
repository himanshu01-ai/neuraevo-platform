"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  taskKeys,
  taskService,
  type ApprovalDecision,
  type TaskCommand,
  type TaskDraft,
} from "@/services/tasks";

/**
 * Server-state hooks for tasks. Each wraps `services/tasks`, so callers never
 * know whether the data came from a mock adapter or a backend.
 *
 * On polling: a running task is live data, and docs/09 says live surfaces poll
 * behind the feature hook. Nothing polls here — the mock advances nothing, so a
 * refetch would return the identical bytes and cost a render for no news. The
 * hook is where that gets switched on in Sprint 17.8, and no component changes
 * when it does.
 */
const LIST_STALE_TIME = 30_000;

export function useTaskList() {
  return useQuery({
    queryKey: taskKeys.lists,
    queryFn: taskService.list,
    staleTime: LIST_STALE_TIME,
  });
}

export function useTaskDetail(id: string | null) {
  return useQuery({
    queryKey: taskKeys.detail(id ?? ""),
    queryFn: () => taskService.detail(id as string),
    staleTime: LIST_STALE_TIME,
    // The directory renders with nothing selected, so the panels ask for a task
    // that may not exist yet. No id, no request.
    enabled: id !== null,
    retry: false,
  });
}

export function useTaskTimeline(id: string | null) {
  return useQuery({
    queryKey: taskKeys.timeline(id ?? ""),
    queryFn: () => taskService.timeline(id as string),
    staleTime: LIST_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

export function useTaskArtifacts(id: string | null) {
  return useQuery({
    queryKey: taskKeys.artifacts(id ?? ""),
    queryFn: () => taskService.artifacts(id as string),
    staleTime: LIST_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

export function useTaskApprovals(id: string | null) {
  return useQuery({
    queryKey: taskKeys.approvals(id ?? ""),
    queryFn: () => taskService.approvals(id as string),
    staleTime: LIST_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

export function useAllApprovals() {
  return useQuery({
    queryKey: taskKeys.allApprovals,
    queryFn: taskService.allApprovals,
    staleTime: LIST_STALE_TIME,
  });
}

export function useTaskQueue() {
  return useQuery({
    queryKey: taskKeys.queue,
    queryFn: taskService.queue,
    staleTime: LIST_STALE_TIME,
  });
}

/** Everything a task's own screens cache, refreshed together. */
function invalidateTask(
  queryClient: ReturnType<typeof useQueryClient>,
  task: { id: string }
) {
  void queryClient.invalidateQueries({ queryKey: taskKeys.lists });
  void queryClient.invalidateQueries({ queryKey: taskKeys.timeline(task.id) });
  void queryClient.invalidateQueries({ queryKey: taskKeys.queue });
}

export function useCreateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (draft: TaskDraft) => taskService.create(draft),
    onSuccess: (created) => {
      queryClient.setQueryData(taskKeys.detail(created.id), created);
      invalidateTask(queryClient, created);
    },
  });
}

export function useDuplicateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => taskService.duplicate(id),
    onSuccess: (clone) => {
      queryClient.setQueryData(taskKeys.detail(clone.id), clone);
      invalidateTask(queryClient, clone);
    },
  });
}

/**
 * Asks the platform to change a task's state. The adapter refuses what the
 * state forbids, so a rejected command surfaces as an error rather than a lie.
 */
export function useTaskCommand() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, command }: { id: string; command: TaskCommand }) => taskService.command(id, command),
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id), task);
      invalidateTask(queryClient, task);
    },
  });
}

export function useAssignWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, workflowId }: { id: string; workflowId: string }) =>
      taskService.assignWorkflow(id, workflowId),
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id), task);
      invalidateTask(queryClient, task);
    },
  });
}

export function useAssignEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, employeeId }: { id: string; employeeId: string }) =>
      taskService.assignEmployee(id, employeeId),
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id), task);
      invalidateTask(queryClient, task);
    },
  });
}

/** The runs a task launched — the workflow platform's own history summaries. */
export function useTaskExecutions(id: string | null) {
  return useQuery({
    queryKey: taskKeys.executions(id ?? ""),
    queryFn: () => taskService.executions(id as string),
    staleTime: LIST_STALE_TIME,
    enabled: id !== null,
    retry: false,
  });
}

/** Everything a run changes, refreshed together: the task, and its history. */
function invalidateRun(
  queryClient: ReturnType<typeof useQueryClient>,
  task: { id: string }
) {
  queryClient.setQueryData(taskKeys.detail(task.id), task);
  void queryClient.invalidateQueries({ queryKey: taskKeys.executions(task.id) });
  void queryClient.invalidateQueries({ queryKey: taskKeys.artifacts(task.id) });
  invalidateTask(queryClient, task);
}

/**
 * Launches the task's attached workflow on the platform's execution engine
 * (Sprint 19). Resolves with the task as the run left it — a run that ran and
 * failed resolves too; only a launch the platform refused rejects.
 */
export function useExecuteTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => taskService.execute(id),
    onSuccess: (task) => invalidateRun(queryClient, task),
  });
}

/** Repeats one of the task's recorded runs. History gains a run; none change. */
export function useRetryTaskExecution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, executionId }: { id: string; executionId: string }) =>
      taskService.retryExecution(id, executionId),
    onSuccess: (task) => invalidateRun(queryClient, task),
  });
}

/**
 * Records a reviewer's decision. A decision can move the task it belongs to, so
 * the task's own caches are refreshed alongside the approval lists.
 */
export function useDecideApproval() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (decision: ApprovalDecision) => taskService.decide(decision),
    onSuccess: (approval) => {
      void queryClient.invalidateQueries({ queryKey: taskKeys.approvals(approval.taskId) });
      void queryClient.invalidateQueries({ queryKey: taskKeys.allApprovals });
      void queryClient.invalidateQueries({ queryKey: taskKeys.detail(approval.taskId) });
      invalidateTask(queryClient, { id: approval.taskId });
    },
  });
}
