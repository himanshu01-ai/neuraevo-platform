"use client";

import { useMemo, useState, type DragEvent } from "react";
import { Blocks } from "lucide-react";
import { NODE_HEIGHT, NODE_WIDTH } from "@/services/workflows";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { useBuilderStore } from "@/store/workflow";
import { NODE_TYPES_BY_CATEGORY, type NodeTypeMeta } from "../models/node-types";
import { STEP_DRAG_TYPE } from "../models/step-drag";

/** Canvas point at the middle of what's currently on screen. */
function viewportCenter() {
  const { viewport, pan, zoom } = useBuilderStore.getState();
  return {
    x: (viewport.width / 2 - pan.x) / zoom - NODE_WIDTH / 2,
    y: (viewport.height / 2 - pan.y) / zoom - NODE_HEIGHT / 2,
  };
}

function StepLibraryItem({ type }: { type: NodeTypeMeta }) {
  const addNode = useBuilderStore((s) => s.addNode);
  const Icon = type.icon;

  const handleDragStart = (event: DragEvent<HTMLButtonElement>) => {
    event.dataTransfer.setData(STEP_DRAG_TYPE, type.kind);
    event.dataTransfer.effectAllowed = "copy";
  };

  return (
    <button
      type="button"
      draggable
      onDragStart={handleDragStart}
      onClick={() => addNode({ kind: type.kind, name: type.label, description: type.description, position: viewportCenter() })}
      title={`Add ${type.label}`}
      className="flex w-full cursor-grab items-start gap-2.5 rounded-md p-2 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
    >
      <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{type.label}</span>
        <span className="block truncate text-xs text-muted-foreground">{type.description}</span>
      </span>
    </button>
  );
}

/**
 * The palette of steps. Drag one onto the canvas to place it exactly, or click
 * to drop it in the middle of the view — clicking matters, because drag-and-drop
 * alone would put the builder out of reach of a keyboard.
 */
export function StepLibrary() {
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return NODE_TYPES_BY_CATEGORY;
    return NODE_TYPES_BY_CATEGORY.map((group) => ({
      category: group.category,
      types: group.types.filter(
        (t) => t.label.toLowerCase().includes(term) || t.description.toLowerCase().includes(term)
      ),
    })).filter((group) => group.types.length > 0);
  }, [query]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b p-3">
        <Input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search steps"
          aria-label="Search steps"
          className="h-9"
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {groups.length === 0 ? (
          <EmptyState compact icon={Blocks} title="No steps match" description="Try a different word." />
        ) : (
          <div className="space-y-4">
            {groups.map((group) => (
              <section key={group.category} aria-labelledby={`lib-${group.category}`}>
                <h3
                  id={`lib-${group.category}`}
                  className="mb-1.5 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {group.category}
                </h3>
                <ul>
                  {group.types.map((type) => (
                    <li key={type.kind}>
                      <StepLibraryItem type={type} />
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
