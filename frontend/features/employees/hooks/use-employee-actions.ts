"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { EmployeeDetail } from "@/services/employees";
import {
  employeeArchived,
  employeeDeleted,
  employeeDuplicated,
  employeeErrorMessage,
  employeeRestored,
} from "../models/employee-messages";
import {
  useArchiveEmployee,
  useDeleteEmployee,
  useDuplicateEmployee,
  useRestoreEmployee,
} from "./use-employees";

/** Enough of an employee to act on it and name it in the result. */
export interface EmployeeRef {
  id: string;
  name: string;
}

export interface EmployeeActionFeedback {
  tone: "success" | "error";
  message: string;
}

export interface UseEmployeeActionsOptions {
  /** Where to go once a clone exists. Omit to stay put and report it instead. */
  onDuplicated?: (clone: EmployeeDetail) => void;
  /** Where to go once an employee is gone. Omit to stay put and report it. */
  onDeleted?: (id: string) => void;
}

/** Which action is in flight, so a button can label itself while it waits. */
export type EmployeeActionKind = "duplicate" | "archive" | "restore" | "delete";

export interface EmployeeActions {
  duplicate: (employee: EmployeeRef) => void;
  archive: (employee: EmployeeRef) => void;
  restore: (employee: EmployeeRef) => void;
  remove: (employee: EmployeeRef) => void;
  /**
   * The outcome of the last action, or `null` if none has finished. Cleared
   * when the next action starts, so it always describes the latest one.
   */
  feedback: EmployeeActionFeedback | null;
  pending: EmployeeActionKind | null;
  /** True while any of the three is in flight. */
  isBusy: boolean;
}

/**
 * Duplicate, archive, restore and delete, with something to show for each.
 *
 * The three surfaces that offer these actions — the directory, the profile and
 * the builder — used to fire the mutations and ignore both halves of the result:
 * a success looked like the row quietly changing, and a failure looked like
 * nothing at all. They share this hook now, so an action always says what it
 * did, and says it the same way everywhere.
 *
 * While one action is in flight the rest are refused rather than queued. These
 * are not operations to run twice by double-clicking, and a disabled button is
 * not enough on its own — the roster's menu items can be triggered from three
 * different cards.
 */
export function useEmployeeActions(options: UseEmployeeActionsOptions = {}): EmployeeActions {
  const { onDuplicated, onDeleted } = options;

  const duplicateMutation = useDuplicateEmployee();
  const archiveMutation = useArchiveEmployee();
  const restoreMutation = useRestoreEmployee();
  const removeMutation = useDeleteEmployee();

  const [feedback, setFeedback] = useState<EmployeeActionFeedback | null>(null);

  const pending: EmployeeActionKind | null = duplicateMutation.isPending
    ? "duplicate"
    : archiveMutation.isPending
      ? "archive"
      : restoreMutation.isPending
        ? "restore"
        : removeMutation.isPending
          ? "delete"
          : null;
  const isBusy = pending !== null;

  // The re-entrancy guard reads a ref rather than closing over `isBusy`, so the
  // three handlers keep the same identity for the life of the screen. The roster
  // memoizes its cards on those handlers; making them change when an action
  // starts would re-render every card in the list to no purpose.
  const busyRef = useRef(false);
  busyRef.current = isBusy;

  const succeed = useCallback((message: string) => setFeedback({ tone: "success", message }), []);
  const fail = useCallback(
    (error: unknown, fallback: string) =>
      setFeedback({ tone: "error", message: employeeErrorMessage(error, fallback) }),
    []
  );

  // `mutate` is referentially stable in React Query v5, so these handlers are
  // too — which is what keeps the memoized cards in the roster from re-rendering
  // on every parent render.
  const { mutate: mutateDuplicate } = duplicateMutation;
  const { mutate: mutateArchive } = archiveMutation;
  const { mutate: mutateRestore } = restoreMutation;
  const { mutate: mutateRemove } = removeMutation;

  const duplicate = useCallback(
    (employee: EmployeeRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateDuplicate(employee.id, {
        onSuccess: (clone) => {
          if (onDuplicated) onDuplicated(clone);
          else succeed(employeeDuplicated(employee.name));
        },
        onError: (error) => fail(error, `${employee.name} couldn't be duplicated.`),
      });
    },
    [mutateDuplicate, onDuplicated, succeed, fail]
  );

  const archive = useCallback(
    (employee: EmployeeRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateArchive(employee.id, {
        onSuccess: () => succeed(employeeArchived(employee.name)),
        onError: (error) => fail(error, `${employee.name} couldn't be archived.`),
      });
    },
    [mutateArchive, succeed, fail]
  );

  const restore = useCallback(
    (employee: EmployeeRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateRestore(employee.id, {
        onSuccess: () => succeed(employeeRestored(employee.name)),
        onError: (error) => fail(error, `${employee.name} couldn't be restored.`),
      });
    },
    [mutateRestore, succeed, fail]
  );

  const remove = useCallback(
    (employee: EmployeeRef) => {
      if (busyRef.current) return;
      setFeedback(null);
      mutateRemove(employee.id, {
        onSuccess: () => {
          if (onDeleted) onDeleted(employee.id);
          else succeed(employeeDeleted(employee.name));
        },
        onError: (error) => fail(error, `${employee.name} couldn't be deleted.`),
      });
    },
    [mutateRemove, onDeleted, succeed, fail]
  );

  return useMemo(
    () => ({ duplicate, archive, restore, remove, feedback, pending, isBusy }),
    [duplicate, archive, restore, remove, feedback, pending, isBusy]
  );
}
