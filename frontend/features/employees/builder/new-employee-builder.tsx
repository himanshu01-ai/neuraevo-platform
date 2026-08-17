"use client";

import { useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useEmployeeBuilderStore } from "@/store/employees";
import { LoadingState } from "@/components/ui/loading-state";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { useEmployeeTemplate } from "../hooks/use-employees";
import { EmployeeBuilder } from "./employee-builder";

/**
 * Creating an employee, optionally from a template (`?template=…`).
 *
 * The draft is reset on arrival so a previous session's leftovers never show up
 * in a new employee, and the template is applied exactly once — a refetch must
 * not overwrite what you've typed since.
 */
export function NewEmployeeBuilder() {
  const searchParams = useSearchParams();
  const templateId = searchParams.get("template");

  const resetDraft = useEmployeeBuilderStore((s) => s.resetDraft);
  const applyTemplate = useEmployeeBuilderStore((s) => s.applyTemplate);
  const appliedRef = useRef<string | null>(null);

  const template = useEmployeeTemplate(templateId);

  useEffect(() => {
    // A blank start: clear whatever the last visit left behind.
    if (!templateId) {
      resetDraft();
      appliedRef.current = null;
    }
  }, [templateId, resetDraft]);

  useEffect(() => {
    if (!template.data) return;
    if (appliedRef.current === template.data.id) return;
    appliedRef.current = template.data.id;
    applyTemplate(template.data);
  }, [template.data, applyTemplate]);

  // Rendering the form before the template lands would show an empty draft that
  // fills itself in a moment later. Wait for it.
  if (templateId && template.isPending) {
    return (
      <WorkspaceContent>
        <LoadingState rows={6} />
      </WorkspaceContent>
    );
  }

  return <EmployeeBuilder mode="create" />;
}
