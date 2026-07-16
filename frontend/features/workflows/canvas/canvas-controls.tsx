"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ZOOM_MAX, ZOOM_MIN } from "@/services/workflows";
import { useBuilderStore } from "@/store/workflow";

/** Zoom and fit controls, docked to the canvas. */
export function CanvasControls() {
  const zoom = useBuilderStore((s) => s.zoom);
  const zoomIn = useBuilderStore((s) => s.zoomIn);
  const zoomOut = useBuilderStore((s) => s.zoomOut);
  const zoomToFit = useBuilderStore((s) => s.zoomToFit);

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

      <Button variant="ghost" size="icon" className="size-8" onClick={zoomToFit} aria-label="Fit to screen">
        <Maximize2 className="size-4" aria-hidden="true" />
      </Button>
    </div>
  );
}
