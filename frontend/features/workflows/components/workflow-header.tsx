import type { ReactNode } from "react";
import type { WorkflowLifecycle } from "@/types/domain";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { StatusBadge } from "@/components/ui/status-badge";

export interface WorkflowHeaderProps {
  title: string;
  description?: string;
  /** The workflow's authoring lifecycle, shown as a badge beside its name. */
  lifecycle?: WorkflowLifecycle;
  actions?: ReactNode;
}

/**
 * Page header for the workflow screens. Wraps the workspace's header rather than
 * restating it, adding the one thing these screens need: the workflow's
 * lifecycle next to its name.
 */
export function WorkflowHeader({ title, description, lifecycle, actions }: WorkflowHeaderProps) {
  return (
    <WorkspaceHeader
      title={
        <span className="flex min-w-0 items-center gap-3">
          <span className="truncate">{title}</span>
          {lifecycle ? <StatusBadge kind="workflow-lifecycle" status={lifecycle} /> : null}
        </span>
      }
      description={description}
      actions={actions}
    />
  );
}
