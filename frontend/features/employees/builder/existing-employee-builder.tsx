"use client";

import { useEffect } from "react";
import { useEmployeeBuilderStore } from "@/store/employees";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { useEmployeeDetail } from "../hooks/use-employees";
import { EmployeeBuilder } from "./employee-builder";

/**
 * Editing an employee. Loads the record, copies it into the draft once, and
 * hands over to the shared form.
 *
 * `hydrate` is a no-op for an employee already in the draft, so a background
 * refetch can't discard edits — the guard lives in the store, where every caller
 * gets it.
 */
export function ExistingEmployeeBuilder({ id }: { id: string }) {
  const query = useEmployeeDetail(id);
  const hydrate = useEmployeeBuilderStore((s) => s.hydrate);

  useEffect(() => {
    if (query.data) hydrate(query.data);
  }, [query.data, hydrate]);

  if (query.isPending) {
    return (
      <WorkspaceContent>
        <LoadingState rows={6} />
      </WorkspaceContent>
    );
  }

  if (query.isError || !query.data) {
    return (
      <WorkspaceContent>
        <ErrorState
          title="Employee not found"
          description="This employee doesn't exist, or it was deleted."
          action={
            <Button variant="outline" href="/workspace/employees">
              Back to employees
            </Button>
          }
        />
      </WorkspaceContent>
    );
  }

  return <EmployeeBuilder mode="edit" />;
}
