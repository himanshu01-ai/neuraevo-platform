"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { workflowKeys, workflowsService, type WorkflowDraft } from "@/services/workflows";

/**
 * Server-state hooks for workflows. Each wraps `services/workflows`, so callers
 * never know whether the data came from a mock adapter or a backend.
 *
 * Templates are immutable fixtures, so they get a long `staleTime`; the list and
 * details are user-owned and refetch more readily.
 */
const LIST_STALE_TIME = 30_000;
const TEMPLATE_STALE_TIME = 600_000;

export function useWorkflowList() {
  return useQuery({
    queryKey: workflowKeys.lists,
    queryFn: workflowsService.list,
    staleTime: LIST_STALE_TIME,
  });
}

export function useWorkflowDetail(id: string) {
  return useQuery({
    queryKey: workflowKeys.detail(id),
    queryFn: () => workflowsService.detail(id),
    staleTime: LIST_STALE_TIME,
    retry: false,
  });
}

export function useWorkflowTemplates() {
  return useQuery({
    queryKey: workflowKeys.templates,
    queryFn: workflowsService.templates,
    staleTime: TEMPLATE_STALE_TIME,
  });
}

export function useWorkflowTemplate(id: string, enabled = true) {
  return useQuery({
    queryKey: workflowKeys.template(id),
    queryFn: () => workflowsService.template(id),
    staleTime: TEMPLATE_STALE_TIME,
    enabled,
  });
}

/** Persists a draft through the service seam and refreshes what it invalidates. */
export function useSaveWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (draft: WorkflowDraft) => workflowsService.save(draft),
    onSuccess: (saved) => {
      queryClient.setQueryData(workflowKeys.detail(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: workflowKeys.lists });
    },
  });
}

export function useDuplicateWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsService.duplicate(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowKeys.lists });
    },
  });
}

/** Releases a draft. The response carries the new lifecycle; cache it. */
export function usePublishWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsService.publish(id),
    onSuccess: (published) => {
      queryClient.setQueryData(workflowKeys.detail(published.id), published);
      void queryClient.invalidateQueries({ queryKey: workflowKeys.lists });
    },
  });
}

/** Returns a published workflow to draft. */
export function useUnpublishWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsService.unpublish(id),
    onSuccess: (draft) => {
      queryClient.setQueryData(workflowKeys.detail(draft.id), draft);
      void queryClient.invalidateQueries({ queryKey: workflowKeys.lists });
    },
  });
}

/** Retires a workflow. Mirrors the employee domain's archive refresh. */
export function useArchiveWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsService.archive(id),
    onSuccess: (archived) => {
      queryClient.setQueryData(workflowKeys.detail(archived.id), archived);
      void queryClient.invalidateQueries({ queryKey: workflowKeys.lists });
    },
  });
}

/** Brings an archived workflow back to the bench. */
export function useRestoreWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsService.restore(id),
    onSuccess: (restored) => {
      queryClient.setQueryData(workflowKeys.detail(restored.id), restored);
      void queryClient.invalidateQueries({ queryKey: workflowKeys.lists });
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsService.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowKeys.lists });
    },
  });
}

/**
 * Runs a published workflow and returns what happened.
 *
 * The workflow itself is not invalidated, and that is deliberate: running a
 * workflow reads it, it does not change it. Its *history* is another matter —
 * a run adds a row to it — so that is invalidated and nothing else.
 *
 * The result lives in this mutation's own state, so there is one copy of it and
 * starting the next run clears the last one.
 */
export function useExecuteWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsService.execute(id),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({
        queryKey: workflowKeys.executions(run.workflowId),
      });
    },
  });
}

/**
 * A workflow's run history, newest first.
 *
 * `staleTime` is zero: history is the one thing here that changes without this
 * client asking, and a list showing a run that already finished elsewhere is
 * the failure this screen exists to avoid.
 */
export function useWorkflowExecutions(id: string, enabled = true) {
  return useQuery({
    queryKey: workflowKeys.executions(id),
    queryFn: () => workflowsService.executions(id),
    enabled: enabled && Boolean(id),
  });
}

/**
 * One recorded run, with its steps and its log.
 *
 * Cached indefinitely and never refetched: a finished run is immutable by
 * design, so once fetched there is nothing new to learn about it. This is also
 * why a live run and a historical one can share one rendering path — the run
 * that just finished is simply the newest immutable record.
 */
export function useWorkflowExecution(executionId: string | null) {
  return useQuery({
    queryKey: workflowKeys.execution(executionId ?? ""),
    queryFn: () => workflowsService.execution(executionId as string),
    enabled: Boolean(executionId),
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * Runs a workflow again, repeating a past run.
 *
 * Creates a new run and leaves the original alone, so nothing already cached is
 * stale except the history it was added to.
 */
export function useRetryWorkflowExecution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (executionId: string) => workflowsService.retry(executionId),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({
        queryKey: workflowKeys.executions(run.workflowId),
      });
    },
  });
}
