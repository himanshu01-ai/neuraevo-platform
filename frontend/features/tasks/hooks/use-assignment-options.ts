"use client";

import { useQuery } from "@tanstack/react-query";
import { employeeKeys, employeesService } from "@/services/employees";
import { workflowKeys, workflowsService } from "@/services/workflows";

/**
 * The real choices the builder and toolbar offer (Sprint 19).
 *
 * Until now assignment pickers listed names hardcoded in the tasks mock; these
 * hooks replace them with the user's actual workflows and AI employees, read
 * through the same services — and the same query keys — the workflow and
 * employee workspaces use, so the caches are one and nothing is fetched twice.
 *
 * Options are display pairs only. The workflow and employee modules own the
 * records; a task carries just the id it points at.
 */
const OPTIONS_STALE_TIME = 30_000;

export interface AssignmentOption {
  id: string;
  name: string;
}

/**
 * Every workflow the user could attach, with drafts labelled as such —
 * attaching a draft is allowed (shaping work is planning), but only a
 * published workflow can run, and the label says so up front.
 */
export function useWorkflowOptions() {
  return useQuery({
    queryKey: workflowKeys.lists,
    queryFn: workflowsService.list,
    staleTime: OPTIONS_STALE_TIME,
    select: (workflows): AssignmentOption[] =>
      workflows
        .filter((workflow) => workflow.lifecycle !== "ARCHIVED")
        .map((workflow) => ({
          id: workflow.id,
          name:
            workflow.lifecycle === "PUBLISHED"
              ? workflow.name
              : `${workflow.name} (draft)`,
        })),
  });
}

/** Every employee who could carry the work. Archived employees don't work. */
export function useEmployeeOptions() {
  return useQuery({
    queryKey: employeeKeys.lists,
    queryFn: employeesService.list,
    staleTime: OPTIONS_STALE_TIME,
    select: (employees): AssignmentOption[] =>
      employees
        .filter((employee) => !employee.isArchived)
        .map((employee) => ({ id: employee.id, name: employee.name })),
  });
}
