"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { WorkflowDetail } from "@/services/workflows";
import {
  workflowArchived,
  workflowDeleted,
  workflowDuplicated,
  workflowErrorMessage,
  workflowPublished,
  workflowRestored,
  workflowUnpublished,
} from "../models/workflow-messages";
import {
  useArchiveWorkflow,
  useDeleteWorkflow,
  useDuplicateWorkflow,
  usePublishWorkflow,
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
  | "delete";

export interface UseWorkflowActionsOptions {
  /** Where to go once a clone exists. Omit to stay put and report it instead. */
  onDuplicated?: (clone: WorkflowDetail) => void;
  /** Where to go once a workflow is gone. Omit to stay put and report it. */
  onDeleted?: (id: string) => void;
}

export interface WorkflowActions {
  duplicate: (workflow: WorkflowRef) => void;
  publish: (workflow: WorkflowRef) => void;
  unpublish: (workflow: WorkflowRef) => void;
  archive: (workflow: WorkflowRef) => void;
  restore: (workflow: WorkflowRef) => void;
  remove: (workflow: WorkflowRef) => void;
  /** The outcome of the last action, cleared when the next one starts. */
  feedback: WorkflowActionFeedback | null;
  pending: WorkflowActionKind | null;
  isBusy: boolean;
}

/**
 * The workflow lifecycle actions, with something to show for each.
 *
 * The same shape as the employee domain's `useEmployeeActions`: the list, the
 * detail page and the builder all offer these, and sharing one hook means an
 * action reports its outcome the same way everywhere and never fires twice
 * from a double-click. Handlers are identity-stable so the memoized cards in
 * the list don't re-render when an action starts.
 */
export function useWorkflowActions(options: UseWorkflowActionsOptions = {}): WorkflowActions {
  const { onDuplicated, onDeleted } = options;

  const duplicateMutation = useDuplicateWorkflow();
  const publishMutation = usePublishWorkflow();
  const unpublishMutation = useUnpublishWorkflow();
  const archiveMutation = useArchiveWorkflow();
  const restoreMutation = useRestoreWorkflow();
  const removeMutation = useDeleteWorkflow();

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

  return useMemo(
    () => ({ duplicate, publish, unpublish, archive, restore, remove, feedback, pending, isBusy }),
    [duplicate, publish, unpublish, archive, restore, remove, feedback, pending, isBusy]
  );
}
