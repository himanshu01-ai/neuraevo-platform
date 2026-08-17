import type { ReactNode } from "react";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import type { EmployeeStatus } from "@/services/employees";
import { EmployeeStatusBadge } from "./employee-status-badge";

export interface EmployeeHeaderProps {
  title: string;
  description?: string;
  status?: EmployeeStatus;
  actions?: ReactNode;
}

/**
 * Page header for the employee screens. Wraps the workspace's header rather than
 * restating it, adding the one thing these screens need: the employee's status
 * next to its name.
 */
export function EmployeeHeader({ title, description, status, actions }: EmployeeHeaderProps) {
  return (
    <WorkspaceHeader
      title={
        <span className="flex min-w-0 items-center gap-3">
          <span className="truncate">{title}</span>
          {status ? <EmployeeStatusBadge status={status} /> : null}
        </span>
      }
      description={description}
      actions={actions}
    />
  );
}
