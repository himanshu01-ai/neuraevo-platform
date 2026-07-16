"use client";

import { useRef } from "react";
import { Blocks, History, Workflow } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useDirectoryStore, type EmployeeDockTab } from "@/store/employees";
import { ActivityTimeline } from "../activity/activity-timeline";
import { AssignmentPanel } from "../assignments/assignment-panel";
import { CapabilityGrid } from "../capabilities/capability-grid";
import { useEmployeeDetail } from "../hooks/use-employees";
import { cn } from "@/lib/utils";

const TABS: { id: EmployeeDockTab; label: string; icon: typeof History }[] = [
  { id: "activity", label: "Activity", icon: History },
  { id: "assignments", label: "Assignments", icon: Workflow },
  { id: "capabilities", label: "Capabilities", icon: Blocks },
];

/**
 * The strip under the split: the selected employee's activity, assignments, and
 * capabilities.
 *
 * A real tablist — arrow keys move between tabs, and each panel is bound to its
 * tab by id. Only the active panel is mounted, so the two you can't see cost
 * nothing to render.
 */
export function EmployeeDock({ employeeId }: { employeeId: string | null }) {
  const dockTab = useDirectoryStore((s) => s.dockTab);
  const setDockTab = useDirectoryStore((s) => s.setDockTab);
  const tablistRef = useRef<HTMLDivElement>(null);

  const detail = useEmployeeDetail(employeeId);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    const direction = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (direction === 0) return;
    event.preventDefault();

    const index = TABS.findIndex((t) => t.id === dockTab);
    const next = TABS[(index + direction + TABS.length) % TABS.length];
    if (!next) return;
    setDockTab(next.id);
    tablistRef.current?.querySelector<HTMLElement>(`#employee-tab-${next.id}`)?.focus();
  };

  const body = () => {
    if (employeeId === null) {
      return (
        <EmptyState
          compact
          icon={History}
          title="Nothing selected"
          description="Pick an employee to see what it's been doing."
        />
      );
    }

    switch (dockTab) {
      case "activity":
        return <ActivityTimeline employeeId={employeeId} limit={6} />;
      case "assignments":
        if (detail.isPending) return <LoadingState rows={4} />;
        if (detail.isError || !detail.data) {
          return (
            <EmptyState
              compact
              icon={Workflow}
              title="Couldn't load assignments"
              description="This employee's assignments couldn't be loaded."
            />
          );
        }
        return <AssignmentPanel assignments={detail.data.assignments} />;
      case "capabilities":
        return <CapabilityGrid employeeId={employeeId} />;
    }
  };

  return (
    <section className="flex min-w-0 flex-col rounded-lg border bg-card shadow-sm">
      <div
        ref={tablistRef}
        role="tablist"
        aria-label="Employee details"
        onKeyDown={handleKeyDown}
        // The three tabs don't fit a 320px screen. They scroll inside their own
        // row rather than widening the page, so every tab stays reachable.
        className="flex items-center gap-1 overflow-x-auto border-b px-2"
      >
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = dockTab === id;
          return (
            <button
              key={id}
              id={`employee-tab-${id}`}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`employee-panel-${id}`}
              // Roving tabindex: one stop for the group, arrows move within it.
              tabIndex={isActive ? 0 : -1}
              onClick={() => setDockTab(id)}
              className={cn(
                "-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          );
        })}
      </div>

      <div
        id={`employee-panel-${dockTab}`}
        role="tabpanel"
        aria-labelledby={`employee-tab-${dockTab}`}
        tabIndex={0}
        className="max-h-80 flex-1 overflow-y-auto p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {body()}
      </div>
    </section>
  );
}
