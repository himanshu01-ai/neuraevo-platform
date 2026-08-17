"use client";

import { useMemo } from "react";
import { useBuilderStore } from "@/store/workflow";
import { validateWorkflow, type ValidationReport } from "../validation/rules";

/**
 * The current draft's validation report, recomputed only when the graph changes.
 *
 * The rules are pure and the graphs are small, so each consumer memoizing its
 * own call is cheaper than threading the report through props — and it keeps the
 * status bar, the validation panel, the inspector, and the canvas independent.
 */
export function useWorkflowValidation(): ValidationReport {
  const graph = useBuilderStore((s) => s.graph);
  return useMemo(() => validateWorkflow(graph), [graph]);
}
