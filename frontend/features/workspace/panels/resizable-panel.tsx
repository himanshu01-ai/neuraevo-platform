"use client";

import { useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ResizablePanelProps {
  children: ReactNode;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  /** Which edge the drag handle sits on. */
  side?: "right" | "left";
  ariaLabel?: string;
  className?: string;
}

/**
 * Future-ready resizable panel: drag or keyboard-resize a fixed-width region.
 * The handle is a focusable `separator` with arrow-key support. Not yet used by
 * a screen — provided for future split layouts (workspace canvas, inspectors).
 */
export function ResizablePanel({
  children,
  defaultWidth = 320,
  minWidth = 240,
  maxWidth = 560,
  side = "right",
  ariaLabel = "Panel",
  className,
}: ResizablePanelProps) {
  const [width, setWidth] = useState(defaultWidth);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startW = useRef(0);

  const clamp = (w: number) => Math.min(maxWidth, Math.max(minWidth, w));
  const dir = side === "right" ? 1 : -1;

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = width;
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) return;
    setWidth(clamp(startW.current + (e.clientX - startX.current) * dir));
  };
  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    dragging.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    const step = (e.shiftKey ? 32 : 16) * dir;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      setWidth((w) => clamp(w - step));
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      setWidth((w) => clamp(w + step));
    }
  };

  const handle = (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={`Resize ${ariaLabel}`}
      aria-valuenow={Math.round(width)}
      aria-valuemin={minWidth}
      aria-valuemax={maxWidth}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onKeyDown={onKeyDown}
      className="group relative w-1.5 shrink-0 cursor-col-resize touch-none select-none focus-visible:outline-none"
    >
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-colors group-hover:bg-primary/50 group-focus-visible:bg-primary"
      />
    </div>
  );

  return (
    <div className={cn("flex", className)}>
      {side === "left" ? handle : null}
      <div style={{ width }} className="min-w-0 shrink-0">
        {children}
      </div>
      {side === "right" ? handle : null}
    </div>
  );
}
