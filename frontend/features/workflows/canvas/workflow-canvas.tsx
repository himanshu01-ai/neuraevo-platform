"use client";

import { useCallback, useEffect, useMemo, useRef, type DragEvent, type KeyboardEvent } from "react";
import {
  GRID_SIZE,
  inputAnchor,
  outputAnchor,
  snap,
  type WorkflowNode as WorkflowNodeModel,
} from "@/services/workflows";
import { useBuilderStore } from "@/store/workflow";
import { useCanvasInteraction } from "../hooks/use-canvas-interaction";
import { NODE_TYPES } from "../models/node-types";
import { isNodeKind, STEP_DRAG_TYPE } from "../models/step-drag";
import { ConnectionMarkers, WorkflowConnection } from "./workflow-connection";
import { CanvasControls } from "./canvas-controls";
import { CanvasMinimap } from "./canvas-minimap";
import { WorkflowNode } from "./workflow-node";
import { cn } from "@/lib/utils";

/** Arrow-key nudge distance for the selected node. */
const NUDGE = GRID_SIZE;

/**
 * The workflow canvas: a grid surface, a pan/zoom transform layer, connections
 * in SVG beneath the nodes, and the controls docked on top.
 *
 * Coordinates: the transform is `translate(pan) scale(zoom)`, so a canvas point
 * lands on screen at `pan + point * zoom`. `useCanvasInteraction` inverts
 * exactly that.
 *
 * Nothing here executes a workflow. It edits structure.
 */
export function WorkflowCanvas({ flaggedNodeIds = [] }: { flaggedNodeIds?: string[] }) {
  const surfaceRef = useRef<HTMLDivElement>(null);

  const nodes = useBuilderStore((s) => s.graph.nodes);
  const edges = useBuilderStore((s) => s.graph.edges);
  const zoom = useBuilderStore((s) => s.zoom);
  const pan = useBuilderStore((s) => s.pan);
  const selectedNodeId = useBuilderStore((s) => s.selectedNodeId);
  const connecting = useBuilderStore((s) => s.connecting);
  const selectNode = useBuilderStore((s) => s.selectNode);
  const setViewport = useBuilderStore((s) => s.setViewport);

  const { startNodeDrag, startPan, startConnect, isPanning } = useCanvasInteraction(surfaceRef);

  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const flagged = useMemo(() => new Set(flaggedNodeIds), [flaggedNodeIds]);

  // Report the surface size so zoom-to-fit and the minimap can do their math.
  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;

    // Measure once up front. ResizeObserver only delivers through the rendering
    // lifecycle, so a page that isn't painting (backgrounded tab, hidden
    // preview) would otherwise leave the viewport at zero and quietly disable
    // zoom-to-fit.
    const rect = element.getBoundingClientRect();
    if (rect.width > 0) setViewport({ width: rect.width, height: rect.height });

    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      setViewport({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [setViewport]);

  // Ctrl/⌘ + wheel zooms about the pointer. Registered natively because it must
  // preventDefault to stop the browser's own page zoom, and React's wheel
  // handler is passive.
  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;

    const handleWheel = (event: WheelEvent) => {
      const store = useBuilderStore.getState();
      const rect = element.getBoundingClientRect();

      if (event.ctrlKey || event.metaKey) {
        event.preventDefault();
        store.setZoom(store.zoom - event.deltaY * 0.002, {
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
        });
        return;
      }

      event.preventDefault();
      store.setPan({ x: store.pan.x - event.deltaX, y: store.pan.y - event.deltaY });
    };

    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => element.removeEventListener("wheel", handleWheel);
  }, []);

  const handleKeyDown = useCallback((event: KeyboardEvent<HTMLDivElement>) => {
    const store = useBuilderStore.getState();
    const id = store.selectedNodeId;
    if (!id) return;

    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      store.deleteNode(id);
      return;
    }

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
      event.preventDefault();
      store.duplicateNode(id);
      return;
    }

    // Arrow keys move the selected step, so the canvas is usable without a mouse.
    const delta: Record<string, [number, number]> = {
      ArrowUp: [0, -NUDGE],
      ArrowDown: [0, NUDGE],
      ArrowLeft: [-NUDGE, 0],
      ArrowRight: [NUDGE, 0],
    };
    const move = delta[event.key];
    if (!move) return;

    const node = store.graph.nodes.find((n) => n.id === id);
    if (!node) return;
    event.preventDefault();
    store.beginNodeDrag();
    store.moveNode(id, { x: snap(node.position.x + move[0]), y: snap(node.position.y + move[1]) });
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const kind = event.dataTransfer.getData(STEP_DRAG_TYPE);
      if (!isNodeKind(kind)) return;

      const rect = surfaceRef.current?.getBoundingClientRect();
      const store = useBuilderStore.getState();
      const meta = NODE_TYPES[kind];

      store.addNode({
        kind,
        name: meta.label,
        description: meta.description,
        position: {
          x: (event.clientX - (rect?.left ?? 0) - store.pan.x) / store.zoom,
          y: (event.clientY - (rect?.top ?? 0) - store.pan.y) / store.zoom,
        },
      });
    },
    []
  );

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }, []);

  return (
    <div
      ref={surfaceRef}
      role="application"
      aria-label="Workflow canvas"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onPointerDown={(event) => {
        // A press that lands on the surface itself clears the selection and pans.
        if (event.target === event.currentTarget || event.target === event.currentTarget.firstChild) {
          selectNode(null);
        }
        startPan(event);
      }}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      className={cn(
        "relative size-full overflow-hidden bg-background outline-none",
        "focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        isPanning ? "cursor-grabbing" : "cursor-grab"
      )}
      style={{
        backgroundImage: "radial-gradient(circle, hsl(var(--border)) 1px, transparent 1px)",
        backgroundSize: `${GRID_SIZE * zoom}px ${GRID_SIZE * zoom}px`,
        backgroundPosition: `${pan.x}px ${pan.y}px`,
      }}
    >
      <div
        className="absolute left-0 top-0 origin-top-left"
        style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
      >
        <svg className="pointer-events-none absolute left-0 top-0 overflow-visible" width="1" height="1">
          <ConnectionMarkers />
          {edges.map((edge) => {
            const source = nodeById.get(edge.sourceNode);
            const target = nodeById.get(edge.targetNode);
            if (!source || !target) return null;
            return (
              <WorkflowConnection
                key={edge.id}
                from={outputAnchor(source)}
                to={inputAnchor(target)}
                isActive={selectedNodeId === edge.sourceNode || selectedNodeId === edge.targetNode}
              />
            );
          })}
          {connecting ? <ConnectingEdge sourceId={connecting.sourceNode} nodeById={nodeById} /> : null}
        </svg>

        {nodes.map((node) => (
          <WorkflowNode
            key={node.id}
            node={node}
            isSelected={selectedNodeId === node.id}
            isFlagged={flagged.has(node.id)}
            isConnectTarget={Boolean(connecting) && connecting?.sourceNode !== node.id}
            onPointerDownCard={startNodeDrag}
            onPointerDownHandle={startConnect}
            onSelect={selectNode}
          />
        ))}
      </div>

      <CanvasControls />
      <CanvasMinimap />
    </div>
  );
}

/** The dashed line that follows the pointer while a connection is being drawn. */
function ConnectingEdge({
  sourceId,
  nodeById,
}: {
  sourceId: string;
  nodeById: Map<string, WorkflowNodeModel>;
}) {
  const pointer = useBuilderStore((s) => s.connecting?.pointer);
  const source = nodeById.get(sourceId);
  if (!source || !pointer) return null;
  return <WorkflowConnection isDraft from={outputAnchor(source)} to={pointer} />;
}
