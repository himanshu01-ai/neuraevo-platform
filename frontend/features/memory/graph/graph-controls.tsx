"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import { ZOOM_MAX, ZOOM_MIN, type KnowledgeGraph } from "@/services/memory";
import { useMemoryStore } from "@/store/memory";
import { Button } from "@/components/ui/button";

/**
 * Zoom and fit controls, docked to the knowledge canvas.
 *
 * Deliberately the same shape and wording as the workflow builder's and the
 * execution canvas's controls: three canvases in one product should be operated
 * the same way, and the zoom bounds come from the same graph module rather than
 * being restated. The component isn't shared because each reads a different
 * store, and reaching across features for one would couple a knowledge map to an
 * editor.
 */
export function GraphControls({ graph }: { graph: KnowledgeGraph }) {
  const zoom = useMemoryStore((s) => s.zoom);
  const zoomIn = useMemoryStore((s) => s.zoomIn);
  const zoomOut = useMemoryStore((s) => s.zoomOut);
  const zoomToFit = useMemoryStore((s) => s.zoomToFit);

  return (
    <div className="absolute bottom-4 left-4 flex items-center gap-0.5 rounded-md border bg-card/95 p-1 shadow-md">
      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={zoomOut}
        disabled={zoom <= ZOOM_MIN}
        aria-label="Zoom out"
      >
        <Minus className="size-4" aria-hidden="true" />
      </Button>

      <span aria-live="polite" className="w-12 text-center text-xs font-medium text-foreground">
        {Math.round(zoom * 100)}%
      </span>

      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={zoomIn}
        disabled={zoom >= ZOOM_MAX}
        aria-label="Zoom in"
      >
        <Plus className="size-4" aria-hidden="true" />
      </Button>

      <span aria-hidden="true" className="mx-1 h-5 w-px bg-border" />

      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={() => zoomToFit(graph)}
        aria-label="Fit to screen"
      >
        <Maximize2 className="size-4" aria-hidden="true" />
      </Button>
    </div>
  );
}
