"use client";

import { useEffect } from "react";
import { useBuilderStore } from "@/store/workflow";
import { WorkflowBuilder } from "./workflow-builder";

/**
 * The builder for a workflow that doesn't exist yet.
 *
 * If the draft still belongs to a saved workflow — you came here from editing
 * one — it's cleared, or "New workflow" would quietly keep editing the old one
 * and Save would overwrite it. A draft with no id is kept: that's a template you
 * just chose, on its way here.
 */
export function NewWorkflowBuilder() {
  useEffect(() => {
    const store = useBuilderStore.getState();
    if (store.workflowId !== null) store.resetDraft();
  }, []);

  return <WorkflowBuilder />;
}
