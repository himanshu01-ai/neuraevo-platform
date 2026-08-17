"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { WorkflowDetail, WorkflowRun } from "@/services/workflows";
import {
  workflowArchived,
  workflowDeleted,
  workflowDuplicated,
  workflowErrorMessage,
  workflowPublished,
  workflowRestored,
  workflowRunErrorMessage,
  workflowUnpublished,
} from "../models/workflow-messages";
import {
  useArchiveWorkflow,
  useDeleteWorkflow,
  useDuplicateWorkflow,
  useExecuteWorkflow,
  usePublishWorkflow,
  useRetryWorkflowExecution,
  useRestoreWorkflow,
  useUnpublishWorkflow,
} from "./use-workflows";

/** Enough of a workflow to act on it and name it in the result. */
export interface WorkflowRef {
  id: string;
  name: string;
}

export interface WorkflowActionFeedback {
  tone: "success" | "error";
  message: string;
}

/** Which action is in flight, so a control can label itself while it waits. */
export type WorkflowActionKind =
  | "duplicate"
  | "publish"
  | "unpublish"
  | "archive"
  | "restore"
  | "delete"
  | "run"
  | "retry";

export interface UseWorkflowActionsOptions {
  /** Where to go once a clone exists. Omit to stay put and report it instead. */
  onDuplicated?: (clone: WorkflowDetail) => void;
  /** Where to go once a workflow is gone. Omit to stay put and report it. */
  onDeleted?: (id: string) => void;
  /**
   * Called with the run a `run` or `retry` just produced (Sprint 18.10).
   * The screen uses it to show that run; the hook keeps no opinion on which
   * one is on display.
   */
  onRan?: (run: WorkflowRun) => void;
}

export interface WorkflowActions {
  duplicate: (workflow: WorkflowRef) => void;
  publish: (workflow: WorkflowRef) => void;
  unpublish: (workflow: WorkflowRef) => void;
  archive: (workflow: WorkflowRef) => void;
  restore: (workflow: WorkflowRef) => void;
  remove: (workflow: WorkflowRef) => void;
  /** Run a published workflow. Draft and archived workflows are refused. */
  run: (workflow: WorkflowRef) => void;
  /** Run the workflow again, repeating a recorded run. */
  retry: (executionId: string) => void;
  /**
   * The last finished run, or `null` before one has happened. Cleared when the
   * next run starts, and left alone by every other action — it belongs to the
   * run, not to the screen.
   */
  lastRun: WorkflowRun | null;
  /** Whether a run is in flight, so its result panel can say so. */
  isRunning: boolean;
  /** The outcome of the last action, cleared when the next one starts. */
  feedback: WorkflowActionFeedback | null;
  pending: WorkflowActionKind | null;
  isBusy: boolean;
}

/**
 * The workflow lifecycle actions — and, since Sprint 18.7, running one — with
 * something to show for each.
 *
 * The same shape as the employee domain's `useEmployeeActions`: the list, the
 * detail page and the builder all offer these, and sharing one hook means an
 * action reports its outcome the same way everywhere and never fires twice
 * from a double-click. Handlers are identity-stable so the memoized cards in
 * the list don't re-render when an action starts.
 *
 * A run shares the same busy state as the rest, so nothing else can be started
 * while a workflow is executing — including a second run.
 */
export function useWorkflowActions(options: UseWorkflowActionsOptions = {}): WorkflowActions {
  const { onDuplicated, onDeleted, onRan } = options;

  const duplicateMutation = useDuplicateWorkflow();
  const publishMutation = usePublishWorkflow();
  const unpublishMutation = useUnpublishWorkflow();
  const archiveMutation = useArchiveWorkflow();
  const restoreMutation = useRestoreWorkflow();
  const removeMutation = useDeleteWorkflow();
  const runMutation = useExecuteWorkflow();
  const retryMutation = useRetryWorkflowExecution();

  const [feedback, setFeedback] = useState<WorkflowActionFeedback | null>(null);

  const pending: WorkflowActionKind | null = duplicateMutation.isPending
    ? "duplicate"
    : publishMutation.isPending
      ? "publish"
      : unpublishMutation.isPending
        ? "unpublish"
        : archiveMutation.isPending
          ? "archive"
          : restoreMutation.isPending
            ? "restore"
            : removeMutation.isPending
              ? "delete"
              : runMutation.isPending
                ? "run"
                : retryMutation.isPending
                  ? "retry"
                  : null;
  const isBusy = pending !== null;

  // The re-entrancy guard reads a ref rather than closing over `isBusy`, so the
  // handlers keep the same identity for the life of the screen.
  const busyRef = useRef(false);
  busyRef.current = isBusy;

  const succeed = useCallback((message: string) => setFeedback({ tone: "success", message }), []);
  const fail = useCallback(
    (error: unknown, fallback: string) =>
      setFeedback({ tone: "error", message: workflowErrorMessage(error, fallback) }),
    []
  );

  const { mutate: mutateDuplicate } = duplicateMutation;
  const { mutate: mutatePublish } = publishMutation;
  const { mutate: mutateUnpublish } = unpublishMutation;
  const { mutate: mutateArchive } = archiveMutation;
  const { mutate: mutateRestore } = restoreMutation;
  const { mutate: mutateRemove } = removeMutation;
  const { mutate: mutateRun } = runMutation;
  const { mutate: mutateRetry } = retryMutation;

  const duplicate = useCallback(
    (workflow: WorkflowRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateDuplicate(workflow.id, {
        onSuccess: (clone) => {
          if (onDuplicated) onDuplicated(clone);
          else succeed(workflowDuplicated(workflow.name));
        },
        onError: (error) => fail(error, `${workflow.name} couldn't be duplicated.`),
      });
    },
    [mutateDuplicate, onDuplicated, succeed, fail]
  );

  const publish = useCallback(
    (workflow: WorkflowRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutatePublish(workflow.id, {
        onSuccess: () => succeed(workflowPublished(workflow.name)),
        onError: (error) => fail(error, `${workflow.name} couldn't be published.`),
      });
    },
    [mutatePublish, succeed, fail]
  );

  const unpublish = useCallback(
    (workflow: WorkflowRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateUnpublish(workflow.id, {
        onSuccess: () => succeed(workflowUnpublished(workflow.name)),
        onError: (error) => fail(error, `${workflow.name} couldn't be moved to draft.`),
      });
    },
    [mutateUnpublish, succeed, fail]
  );

  const archive = useCallback(
    (workflow: WorkflowRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateArchive(workflow.id, {
        onSuccess: () => succeed(workflowArchived(workflow.name)),
        onError: (error) => fail(error, `${workflow.name} couldn't be archived.`),
      });
    },
    [mutateArchive, succeed, fail]
  );

  const restore = useCallback(
    (workflow: WorkflowRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateRestore(workflow.id, {
        onSuccess: () => succeed(workflowRestored(workflow.name)),
        onError: (error) => fail(error, `${workflow.name} couldn't be restored.`),
      });
    },
    [mutateRestore, succeed, fail]
  );

  const remove = useCallback(
    (workflow: WorkflowRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateRemove(workflow.id, {
        onSuccess: () => {
          if (onDeleted) onDeleted(workflow.id);
          else succeed(workflowDeleted(workflow.name));
        },
        onError: (error) => fail(error, `${workflow.name} couldn't be deleted.`),
      });
    },
    [mutateRemove, onDeleted, succeed, fail]
  );

  /**
   * Running is the one action whose outcome isn't a sentence.
   *
   * A run that started reports itself through `lastRun`, however it ended — a
   * failed run is a result, not an action error, and the panel that renders it
   * says more than a feedback line could. Only a run that never started sets
   * `feedback`, which is exactly what every other action does when it's refused.
   */
  const run = useCallback(
    (workflow: WorkflowRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateRun(workflow.id, {
        onSuccess: (run) => onRan?.(run),
        onError: (error) => fail(error, `${workflow.name} couldn't be run.`),
      });
    },
    [mutateRun, onRan, fail]
  );

  /**
   * Repeat a recorded run.
   *
   * The workflow runs as it is *now*, not as it was, so this can be refused
   * where the original succeeded — unpublished since, or edited into something
   * that no longer runs. Those refusals are reported like any other.
   */
  const retry = useCallback(
    (executionId: string) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateRetry(executionId, {
        onSuccess: (run) => onRan?.(run),
        onError: (error) =>
          setFeedback({
            tone: "error",
            message: workflowRunErrorMessage(error, "That run couldn't be repeated."),
          }),
      });
    },
    [mutateRetry, onRan]
  );

  // The run's own state is the mutation's, so there is never a second copy to
  // keep in step: starting a run clears the previous result on its own.
  const lastRun = runMutation.data ?? null;
  const isRunning = runMutation.isPending || retryMutation.isPending;

  return useMemo(
    () => ({
      duplicate,
      publish,
      unpublish,
      archive,
      restore,
      remove,
      run,
      retry,
      lastRun,
      isRunning,
      feedback,
      pending,
      isBusy,
    }),
    [
      duplicate,
      publish,
      unpublish,
      archive,
      restore,
      remove,
      run,
      retry,
      lastRun,
      isRunning,
      feedback,
      pending,
      isBusy,
    ]
  );
}
