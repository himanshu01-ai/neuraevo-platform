"use client";

import { useCallback, useEffect, useMemo, useRef, type PointerEvent as ReactPointerEvent } from "react";
import { Workflow } from "lucide-react";
import { GRID_SIZE } from "@/services/workflows";
import { isEdgeOnPath, type ExecutionGraph as ExecutionGraphModel, type ExecutionMonitor } from "@/services/tasks";
import { useExecutionStore } from "@/store/tasks";
import { EmptyState } from "@/components/ui/empty-state";
import { ExecutionEdgeLine, ExecutionEdgeMarkers } from "./execution-edge";
import { ExecutionNodeCard } from "./execution-node";
import { ExecutionControls } from "./execution-controls";
import { cn } from "@/lib/utils";

export interface ExecutionGraphProps {
  graph: ExecutionGraphModel;
  monitor: ExecutionMonitor;
  taskId: string;
  className?: string;
}

/**
 * The run, drawn.
 *
 * Read-only: nodes can be selected and the view can be panned and zoomed, but
 * nothing here changes the graph, because the graph is the platform's account of
 * what happened. Edges the run actually travelled are drawn in the success tone
 * and thicker, so the path reads at a glance without hunting node by node.
 *
 * The canvas is one transformed layer rather than per-node transforms: panning
 * moves a single element, so a graph of any size costs one composited change.
 * Nodes are memoized, so a run advancing re-renders the node that moved.
 *
 * Accessibility: the SVG is decorative (`aria-hidden`) because a path can't be
 * focused or read usefully; every node is a real button in the DOM, so the graph
 * is fully traversable with Tab, and the inspector states each node's
 * connections in words.
 */
export function ExecutionGraph({ graph, monitor, taskId, className }: ExecutionGraphProps) {
  const frameRef = useRef<HTMLDivElement>(null);
  const panOrigin = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const zoom = useExecutionStore((s) => s.zoom);
  const pan = useExecutionStore((s) => s.pan);
  const selectedNodeId = useExecutionStore((s) => s.selectedNodeId);
  const focusTask = useExecutionStore((s) => s.focusTask);
  const selectNode = useExecutionStore((s) => s.selectNode);
  const setViewport = useExecutionStore((s) => s.setViewport);
  const setPan = useExecutionStore((s) => s.setPan);
  const setZoom = useExecutionStore((s) => s.setZoom);

  // A different task means a different picture; the store resets the frame once.
  useEffect(() => {
    focusTask(taskId);
  }, [taskId, focusTask]);

  // Keep the store's viewport in step with the element, so zoom-to-fit has real
  // dimensions to work with.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;

    const measure = () => setViewport({ width: frame.clientWidth, height: frame.clientHeight });
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(frame);
    return () => observer.disconnect();
  }, [setViewport]);

  const nodeIndex = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph.nodes]);

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      // Only a drag on the background pans; a press on a node is a selection.
      if (event.target !== event.currentTarget) return;
      panOrigin.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [pan.x, pan.y]
  );

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const origin = panOrigin.current;
      if (!origin) return;
      setPan({ x: origin.panX + (event.clientX - origin.x), y: origin.panY + (event.clientY - origin.y) });
    },
    [setPan]
  );

  const handlePointerUp = useCallback(() => {
    panOrigin.current = null;
  }, []);

  const handleWheel = useCallback(
    (event: React.WheelEvent<HTMLDivElement>) => {
      // Only zoom on an intentional pinch/ctrl-scroll; a plain wheel should still
      // scroll the page the graph sits in.
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const rect = frameRef.current?.getBoundingClientRect();
      if (!rect) return;
      setZoom(zoom - event.deltaY * 0.002, { x: event.clientX - rect.left, y: event.clientY - rect.top });
    },
    [zoom, setZoom]
  );

  if (graph.nodes.length === 0) {
    return (
      <div className={cn("flex min-h-64 items-center justify-center rounded-lg border bg-card", className)}>
        <EmptyState
          icon={Workflow}
          title="Nothing to run yet"
          description="Assign a workflow and an employee, and the run will be drawn here."
        />
      </div>
    );
  }

  return (
    <div className={cn("relative overflow-hidden rounded-lg border bg-background", className)}>
      <div
        ref={frameRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onWheel={handleWheel}
        className="absolute inset-0 cursor-grab touch-none active:cursor-grabbing"
        style={{
          backgroundImage: "radial-gradient(circle, hsl(var(--border)) 1px, transparent 1px)",
          backgroundSize: `${GRID_SIZE * zoom}px ${GRID_SIZE * zoom}px`,
          backgroundPosition: `${pan.x}px ${pan.y}px`,
        }}
      >
        {/* One transformed layer: panning moves this, not every node. */}
        <div
          className="absolute origin-top-left"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
        >
          <svg aria-hidden="true" className="pointer-events-none absolute overflow-visible">
            <ExecutionEdgeMarkers />
            {graph.edges.map((edge) => {
              const from = nodeIndex.get(edge.sourceNode);
              const to = nodeIndex.get(edge.targetNode);
              if (!from || !to) return null;
              return (
                <ExecutionEdgeLine
                  key={edge.id}
                  from={from}
                  to={to}
                  isOnPath={isEdgeOnPath(monitor.executionPath, edge.sourceNode, edge.targetNode)}
                  isActive={selectedNodeId === edge.sourceNode || selectedNodeId === edge.targetNode}
                />
              );
            })}
          </svg>

          {graph.nodes.map((node) => (
            <ExecutionNodeCard
              key={node.id}
              node={node}
              isSelected={selectedNodeId === node.id}
              isCurrent={monitor.currentNodeId === node.id}
              onSelect={selectNode}
            />
          ))}
        </div>
      </div>

      <ExecutionControls graph={graph} />
    </div>
  );
}
