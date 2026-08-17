"use client";

import { useRef } from "react";
import { FileStack, Flag, History, ShieldCheck } from "lucide-react";
import type { TaskDetail } from "@/services/tasks";
import { useTaskStore, type TaskDockTab } from "@/store/tasks";
import { EmptyState } from "@/components/ui/empty-state";
import { ApprovalList } from "../approvals/approval-list";
import { ArtifactList } from "../artifacts/artifact-list";
import { ExecutionTimeline } from "../timeline/execution-timeline";
import { ResultsPanel } from "./results-panel";
import { cn } from "@/lib/utils";

const TABS: { id: TaskDockTab; label: string; icon: typeof History }[] = [
  { id: "timeline", label: "Timeline", icon: History },
  { id: "artifacts", label: "Artifacts", icon: FileStack },
  { id: "approvals", label: "Approvals", icon: ShieldCheck },
  { id: "results", label: "Results", icon: Flag },
];

/**
 * The strip under the split: the selected task's timeline, artifacts, approvals
 * and results.
 *
 * A real tablist — arrow keys move between tabs, and each panel is bound to its
 * tab by id. Only the active panel is mounted, so the three you can't see cost
 * nothing to render and fetch nothing.
 */
export function TaskDock({ task }: { task: TaskDetail | null }) {
  const dockTab = useTaskStore((s) => s.dockTab);
  const setDockTab = useTaskStore((s) => s.setDockTab);
  const tablistRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    const direction = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (direction === 0) return;
    event.preventDefault();

    const index = TABS.findIndex((t) => t.id === dockTab);
    const next = TABS[(index + direction + TABS.length) % TABS.length];
    if (!next) return;
    setDockTab(next.id);
    tablistRef.current?.querySelector<HTMLElement>(`#task-tab-${next.id}`)?.focus();
  };

  const body = () => {
    if (!task) {
      return (
        <EmptyState
          compact
          icon={History}
          title="Nothing selected"
          description="Pick a task to see what it's been doing."
        />
      );
    }

    switch (dockTab) {
      case "timeline":
        return <ExecutionTimeline taskId={task.id} graph={task.graph} limit={6} />;
      case "artifacts":
        return <ArtifactList taskId={task.id} />;
      case "approvals":
        return <ApprovalList taskId={task.id} />;
      case "results":
        return <ResultsPanel task={task} />;
    }
  };

  return (
    <section className="flex min-w-0 flex-col rounded-lg border bg-card shadow-sm">
      <div
        ref={tablistRef}
        role="tablist"
        aria-label="Task details"
        onKeyDown={handleKeyDown}
        // Four tabs don't fit a narrow screen. They scroll inside their own row
        // rather than widening the page, so every tab stays reachable.
        className="flex items-center gap-1 overflow-x-auto border-b px-2"
      >
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = dockTab === id;
          return (
            <button
              key={id}
              id={`task-tab-${id}`}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`task-panel-${id}`}
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
        id={`task-panel-${dockTab}`}
        role="tabpanel"
        aria-labelledby={`task-tab-${dockTab}`}
        tabIndex={0}
        className="max-h-96 flex-1 overflow-y-auto p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {body()}
      </div>
    </section>
  );
}
