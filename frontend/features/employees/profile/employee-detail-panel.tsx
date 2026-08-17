"use client";

import { motion } from "framer-motion";
import { Pencil, UserRoundSearch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useEmployeeDetail } from "../hooks/use-employees";
import { EmployeeProfileLoading } from "../components/employee-loading-state";
import { ProfileConfiguration } from "./profile-configuration";
import { ProfileMemory } from "./profile-memory";
import { ProfileOverview } from "./profile-overview";
import { ProfilePermissions } from "./profile-permissions";

export interface EmployeeDetailPanelProps {
  employeeId: string | null;
}

/**
 * The directory's right-hand column: the selected employee at rest.
 *
 * It shows the sections the dock below doesn't — overview, configuration,
 * memory, permissions — so the two never say the same thing twice. Assignments,
 * activity and capabilities live in the dock; the full profile page shows all
 * seven together.
 *
 * The panel cross-fades on selection, keyed by employee, so switching reads as a
 * change of subject rather than a reflow. Reduced motion collapses it to a cut.
 */
export function EmployeeDetailPanel({ employeeId }: EmployeeDetailPanelProps) {
  const query = useEmployeeDetail(employeeId);

  if (employeeId === null) {
    return (
      <EmptyState
        icon={UserRoundSearch}
        title="No employee selected"
        description="Pick someone from the list to see how they're set up."
      />
    );
  }

  if (query.isPending) return <EmployeeProfileLoading />;

  if (query.isError || !query.data) {
    return (
      <ErrorState
        title="Couldn't load this employee"
        description="This employee doesn't exist, or it was deleted."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const employee = query.data;

  return (
    <motion.div
      key={employee.id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-6"
    >
      <ProfileOverview employee={employee} />

      <div className="flex flex-wrap gap-2">
        <Button size="sm" href={`/workspace/employees/${employee.id}`}>
          Open profile
        </Button>
        <Button variant="outline" size="sm" href={`/workspace/employees/${employee.id}/edit`}>
          <Pencil className="size-4" aria-hidden="true" />
          Edit
        </Button>
      </div>

      <section className="border-t pt-5">
        <h3 className="text-sm font-semibold text-foreground">Configuration</h3>
        <ProfileConfiguration configuration={employee.configuration} className="mt-3" />
      </section>

      <section className="border-t pt-5">
        <h3 className="text-sm font-semibold text-foreground">Memory</h3>
        <ProfileMemory memory={employee.memory} className="mt-3" />
      </section>

      <section className="border-t pt-5">
        <h3 className="text-sm font-semibold text-foreground">Permissions</h3>
        <ProfilePermissions permissions={employee.permissions} className="mt-3 -mx-2" />
      </section>
    </motion.div>
  );
}
