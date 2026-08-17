"use client";

import { useRef } from "react";
import { ChartNoAxesCombined, History, Info, Share2 } from "lucide-react";
import type { KnowledgeGraph, MemoryDetail } from "@/services/memory";
import { useMemoryStore, type MemoryDockTab } from "@/store/memory";
import { EmptyState } from "@/components/ui/empty-state";
import { InsightsPanel } from "../insights/insights-panel";
import { MemoryInspector } from "./memory-inspector";
import { MemoryTimeline } from "../timeline/memory-timeline";
import { RelationshipList } from "./relationship-list";
import { cn } from "@/lib/utils";

const TABS: { id: MemoryDockTab; label: string; icon: typeof History }[] = [
  { id: "timeline", label: "Timeline", icon: History },
  { id: "relationships", label: "Relationships", icon: Share2 },
  { id: "insights", label: "Insights", icon: ChartNoAxesCombined },
  { id: "metadata", label: "Metadata", icon: Info },
];

export interface MemoryDockProps {
  memory: MemoryDetail | null;
  graph?: KnowledgeGraph;
}

/**
 * The strip under the split: the selected memory's history, what it touches, how
 * the knowledge looks as a whole, and its metadata.
 *
 * A real tablist — arrow keys move between tabs, and each panel is bound to its
 * tab by id. Only the active panel is mounted, so the three you can't see cost
 * nothing to render and fetch nothing.
 *
 * Insights is the one tab that doesn't need a selection: it's about the whole
 * workspace, so it stays useful with nothing picked.
 */
export function MemoryDock({ memory, graph }: MemoryDockProps) {
  const dockTab = useMemoryStore((s) => s.dockTab);
  const setDockTab = useMemoryStore((s) => s.setDockTab);
  const tablistRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    const direction = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (direction === 0) return;
    event.preventDefault();

    const index = TABS.findIndex((t) => t.id === dockTab);
    const next = TABS[(index + direction + TABS.length) % TABS.length];
    if (!next) return;
    setDockTab(next.id);
    tablistRef.current?.querySelector<HTMLElement>(`#memory-tab-${next.id}`)?.focus();
  };

  const needsSelection = (
    <EmptyState
      compact
      icon={Info}
      title="Nothing selected"
      description="Pick a memory to see this."
    />
  );

  const body = () => {
    switch (dockTab) {
      case "timeline":
        return <MemoryTimeline memoryId={memory?.id ?? null} limit={6} showMemory={!memory} />;
      case "relationships":
        return memory && graph ? <RelationshipList memory={memory} graph={graph} /> : needsSelection;
      case "insights":
        return <InsightsPanel compact />;
      case "metadata":
        return memory ? <MemoryInspector memory={memory} graph={graph} /> : needsSelection;
    }
  };

  return (
    <section className="flex min-w-0 flex-col rounded-lg border bg-card shadow-sm">
      <div
        ref={tablistRef}
        role="tablist"
        aria-label="Knowledge details"
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
              id={`memory-tab-${id}`}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`memory-panel-${id}`}
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
        id={`memory-panel-${dockTab}`}
        role="tabpanel"
        aria-labelledby={`memory-tab-${dockTab}`}
        tabIndex={0}
        className="max-h-96 flex-1 overflow-y-auto p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {body()}
      </div>
    </section>
  );
}
