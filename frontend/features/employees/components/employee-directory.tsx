"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { LayoutTemplate, Plus } from "lucide-react";
import { EMPLOYEE_STATUS_LABEL } from "@/services/employees";
import { hasActiveFilters, useDirectoryStore } from "@/store/employees";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Reveal } from "@/components/motion/reveal";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { useEmployeeActions } from "../hooks/use-employee-actions";
import { useEmployeeList } from "../hooks/use-employees";
import { useFilteredEmployees } from "../hooks/use-filtered-employees";
import { EmployeeEmptyState } from "./employee-empty-state";
import { EmployeeFilters } from "./employee-filters";
import { EmployeeHeader } from "./employee-header";
import { EmployeeList } from "./employee-list";
import { EmployeeCardGridLoading, EmployeeListLoading, EmployeeProfileLoading } from "./employee-loading-state";

/**
 * The employee directory: the roster on the left, whoever's selected on the
 * right, and their activity, assignments and capabilities in the dock below.
 *
 * The two panels beside and below the list are the heavy half of this screen and
 * neither is needed to render the roster, so both load on demand — the list
 * paints first, and the panels arrive with their own placeholders.
 *
 * Below `lg` the panes stack in reading order (roster, details, dock) rather
 * than switching on a media query: a layout that only depends on CSS can't
 * disagree with the server about what to render on first paint.
 *
 * Duplicating, archiving and deleting live here rather than in the roster
 * because their result has to outlive the card it was triggered from — deleting
 * the last employee replaces the whole list with an empty state, and the
 * confirmation still needs somewhere to appear.
 */

const EmployeeDetailPanel = dynamic(
  () => import("../profile/employee-detail-panel").then((m) => m.EmployeeDetailPanel),
  { loading: () => <EmployeeProfileLoading /> }
);

const EmployeeDock = dynamic(() => import("./employee-dock").then((m) => m.EmployeeDock), {
  loading: () => <div className="h-56 rounded-lg border bg-card shadow-sm" />,
});

export function EmployeeDirectory() {
  const query = useEmployeeList();
  const filters = useDirectoryStore((s) => s.filters);
  const viewMode = useDirectoryStore((s) => s.viewMode);
  const selectedEmployeeId = useDirectoryStore((s) => s.selectedEmployeeId);
  const selectEmployee = useDirectoryStore((s) => s.selectEmployee);

  const employees = useFilteredEmployees(query.data, filters);
  const actions = useEmployeeActions();

  // A selection outlives the roster it came from: an employee deleted here or in
  // another tab, or filtered out of view, would otherwise leave the panel
  // showing someone who isn't in the list. Drop the selection when it stops
  // being real — one rule, rather than each action remembering to clear up.
  useEffect(() => {
    if (!query.data || selectedEmployeeId === null) return;
    if (!query.data.some((employee) => employee.id === selectedEmployeeId)) {
      selectEmployee(null);
    }
  }, [query.data, selectedEmployeeId, selectEmployee]);

  const roster = () => {
    if (query.isError) {
      return (
        <ErrorState
          title="Couldn't load employees"
          description="Your employees couldn't be loaded. Try again in a moment."
          onRetry={() => void query.refetch()}
        />
      );
    }

    if (query.isPending) {
      return viewMode === "grid" ? (
        <EmployeeCardGridLoading count={3} className="sm:grid-cols-1 xl:grid-cols-1" />
      ) : (
        <EmployeeListLoading />
      );
    }

    if (query.data.length === 0) return <EmployeeEmptyState />;

    if (employees.length === 0) {
      // Narrowing to one status and finding nothing is a different fact from a
      // search that missed, so say which — "no archived employees" is an answer,
      // "no matches" is a shrug.
      const onlyStatus =
        filters.status !== "ALL" &&
        !hasActiveFilters({ ...filters, status: "ALL" }) &&
        EMPLOYEE_STATUS_LABEL[filters.status].toLowerCase();

      return (
        <EmployeeEmptyState
          compact
          title={onlyStatus ? `No ${onlyStatus} employees` : "No employees match"}
          description={
            onlyStatus
              ? "Nothing is in that state right now. Try another status."
              : "Try a different word, or clear the filters."
          }
          showActions={false}
        />
      );
    }

    return (
      <EmployeeList
        employees={employees}
        viewMode={viewMode}
        onDuplicate={actions.duplicate}
        onArchive={actions.archive}
        onDelete={actions.remove}
      />
    );
  };

  return (
    <WorkspaceContent>
      <Reveal>
        <EmployeeHeader
          title="AI Employees"
          description="Hire the help you need, give it what it takes to work, and see what it's doing."
          actions={
            <>
              <Button variant="outline" href="/workspace/employees/templates">
                <LayoutTemplate className="size-4" aria-hidden="true" />
                Templates
              </Button>
              <Button href="/workspace/employees/new">
                <Plus className="size-4" aria-hidden="true" />
                New employee
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

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <div className="min-w-0 lg:w-[22rem] lg:shrink-0 xl:w-[24rem]">
          <EmployeeFilters />
          <div className="mt-4">{roster()}</div>
        </div>

        <div className="min-w-0 flex-1">
          <section
            aria-label="Employee details"
            className="rounded-lg border bg-card p-5 shadow-sm lg:sticky lg:top-6"
          >
            <EmployeeDetailPanel employeeId={selectedEmployeeId} />
          </section>
        </div>
      </div>

      <div className="mt-6">
        <EmployeeDock employeeId={selectedEmployeeId} />
      </div>
    </WorkspaceContent>
  );
}
