"use client";

import { useState } from "react";
import { ArrowLeft, Archive, Copy, Pencil } from "lucide-react";
import { useRouter } from "next/navigation";
import { UNSUPPORTED_ACTION_HINT, employeesService } from "@/services/employees";
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
import {
  useArchiveEmployee,
  useDuplicateEmployee,
  useEmployeeDetail,
} from "../hooks/use-employees";
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
  const duplicate = useDuplicateEmployee();
  const archive = useArchiveEmployee();
  const support = employeesService.support;
  const [notice, setNotice] = useState<string | null>(null);

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

  const handleDuplicate = () => {
    duplicate.mutate(employee.id, {
      onSuccess: (clone) => router.push(`/workspace/employees/${clone.id}`),
    });
  };

  const handleArchive = () => {
    archive.mutate(employee.id, {
      onSuccess: () => setNotice(`${employee.name} was archived and taken off its workflows.`),
    });
  };

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
              <Button variant="outline" onClick={handleDuplicate} disabled={duplicate.isPending}>
                <Copy className="size-4" aria-hidden="true" />
                {duplicate.isPending ? "Duplicating…" : "Duplicate"}
              </Button>
              <Button
                variant="outline"
                onClick={handleArchive}
                disabled={archive.isPending || employee.status === "OFFLINE" || !support.archive}
                title={support.archive ? undefined : UNSUPPORTED_ACTION_HINT}
              >
                <Archive className="size-4" aria-hidden="true" />
                Archive
              </Button>
              {/* A link can't be disabled, so an unsupported edit renders as a
                  disabled button rather than a dead-end navigation. */}
              {support.update ? (
                <Button href={`/workspace/employees/${employee.id}/edit`}>
                  <Pencil className="size-4" aria-hidden="true" />
                  Edit
                </Button>
              ) : (
                <Button disabled title={UNSUPPORTED_ACTION_HINT}>
                  <Pencil className="size-4" aria-hidden="true" />
                  Edit
                </Button>
              )}
            </>
          }
        />
      </Reveal>

      {notice ? (
        <p role="status" className="mt-4 rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          {notice}
        </p>
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
