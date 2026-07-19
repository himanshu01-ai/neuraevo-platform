"use client";

import { ArrowLeft, Archive, Copy, Pencil } from "lucide-react";
import { useRouter } from "next/navigation";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { ActivityTimeline } from "../activity/activity-timeline";
import { AssignmentPanel } from "../assignments/assignment-panel";
import { CapabilityGrid } from "../capabilities/capability-grid";
import { EmployeeHeader } from "../components/employee-header";
import { EmployeeProfileLoading } from "../components/employee-loading-state";
import { useEmployeeActions } from "../hooks/use-employee-actions";
import { useEmployeeDetail } from "../hooks/use-employees";
import { roleLabel } from "../models/employee-roles";
import { ProfileConfiguration } from "./profile-configuration";
import { ProfileMemory } from "./profile-memory";
import { ProfileOverview } from "./profile-overview";
import { ProfilePermissions } from "./profile-permissions";

/**
 * One employee in full: all seven profile sections on a single page.
 *
 * The directory splits these across a details column and a dock; here they're
 * together, because this page exists for the moment you want the whole picture.
 * Read-only — every change goes through the builder.
 */
export function EmployeeProfile({ id }: { id: string }) {
  const router = useRouter();
  const query = useEmployeeDetail(id);
  // A clone is a different employee, so duplicating navigates to it; archiving
  // keeps you here and reports what changed.
  const actions = useEmployeeActions({
    onDuplicated: (clone) => router.push(`/workspace/employees/${clone.id}`),
  });

  if (query.isPending) {
    return (
      <WorkspaceContent>
        <EmployeeProfileLoading />
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

  const employee = query.data;
  const isArchived = employee.status === "OFFLINE";

  return (
    <WorkspaceContent>
      <Reveal>
        <EmployeeHeader
          title={employee.name}
          description={roleLabel(employee.role, employee.customRole)}
          status={employee.status}
          actions={
            <>
              <Button variant="ghost" size="icon" href="/workspace/employees" aria-label="Back to employees">
                <ArrowLeft className="size-4" aria-hidden="true" />
              </Button>
              <Button
                variant="outline"
                onClick={() => actions.duplicate(employee)}
                disabled={actions.isBusy}
              >
                <Copy className="size-4" aria-hidden="true" />
                {actions.pending === "duplicate" ? "Duplicating…" : "Duplicate"}
              </Button>
              <Button
                variant="outline"
                onClick={() => actions.archive(employee)}
                disabled={actions.isBusy || isArchived}
                // A disabled control should say why it can't be used.
                title={isArchived ? "This employee is already archived." : undefined}
              >
                <Archive className="size-4" aria-hidden="true" />
                {actions.pending === "archive" ? "Archiving…" : "Archive"}
              </Button>
              <Button href={`/workspace/employees/${employee.id}/edit`}>
                <Pencil className="size-4" aria-hidden="true" />
                Edit
              </Button>
            </>
          }
        />
      </Reveal>

      {actions.feedback ? (
        <Alert
          variant={actions.feedback.tone === "error" ? "error" : "success"}
          className="mt-4"
        >
          {actions.feedback.message}
        </Alert>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <Reveal>
            <Panel title="Overview">
              <ProfileOverview employee={employee} />
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel
              title="Capabilities"
              description="What this employee can be asked to do, and what the platform offers."
            >
              <CapabilityGrid employeeId={employee.id} />
            </Panel>
          </Reveal>

          <Reveal delay={0.05}>
            <Panel title="Assigned workflows" description="Assignment only — the platform runs the work.">
              <AssignmentPanel assignments={employee.assignments} />
            </Panel>
          </Reveal>
        </div>

        <div className="min-w-0 space-y-6">
          <Reveal delay={0.05}>
            <Panel title="Activity" description="Newest first.">
              <ActivityTimeline employeeId={employee.id} />
            </Panel>
          </Reveal>

          <Reveal delay={0.1}>
            <Panel title="Configuration">
              <ProfileConfiguration configuration={employee.configuration} />
            </Panel>
          </Reveal>

          <Reveal delay={0.1}>
            <Panel title="Memory">
              <ProfileMemory memory={employee.memory} />
            </Panel>
          </Reveal>

          <Reveal delay={0.1}>
            <Panel title="Permissions" description="What it may do without asking.">
              <ProfilePermissions permissions={employee.permissions} className="-mx-2" />
            </Panel>
          </Reveal>
        </div>
      </div>
    </WorkspaceContent>
  );
}
