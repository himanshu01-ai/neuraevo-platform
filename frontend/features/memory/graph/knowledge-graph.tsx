"use client";

import { useCallback, useEffect, useMemo, useRef, type PointerEvent as ReactPointerEvent } from "react";
import { Share2 } from "lucide-react";
import { GRID_SIZE } from "@/services/workflows";
import { isEdgeTouching, layoutGraph, neighbourhood, type KnowledgeGraph as KnowledgeGraphModel } from "@/services/memory";
import { useMemoryStore } from "@/store/memory";
import { EmptyState } from "@/components/ui/empty-state";
import { KnowledgeGraphEdge, KnowledgeGraphMarkers } from "./graph-edge";
import { KnowledgeGraphNode } from "./graph-node";
import { GraphControls } from "./graph-controls";
import { cn } from "@/lib/utils";

export interface KnowledgeGraphProps {
  graph: KnowledgeGraphModel;
  /**
   * Narrow the map to one memory and what it touches. `null` shows everything.
   */
  focusMemoryId?: string | null;
  /** Draw relationship names on the edges. Off where space is tight. */
  showLabels?: boolean;
  className?: string;
}

/**
 * How the knowledge hangs together, drawn.
 *
 * Read-only: relationships are a description, not something authored here. The
 * view can be panned and zoomed and nodes can be selected; nothing changes the
 * graph.
 *
 * The canvas is one transformed layer rather than per-node transforms: panning
 * moves a single element, so a map of any size costs one composited change.
 * Nodes and edges are memoized, so selecting one re-renders the ones whose props
 * actually changed.
 *
 * Accessibility: the SVG is decorative (`aria-hidden`) because a path can't be
 * focused or read usefully; every node is a real button in the DOM, so the map
 * is fully traversable with Tab, and the inspector states each node's
 * relationships in words.
 */
export function KnowledgeGraph({
  graph,
  focusMemoryId = null,
  showLabels = false,
  className,
}: KnowledgeGraphProps) {
  const frameRef = useRef<HTMLDivElement>(null);
  const panOrigin = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const zoom = useMemoryStore((s) => s.zoom);
  const pan = useMemoryStore((s) => s.pan);
  const selectedGraphNodeId = useMemoryStore((s) => s.selectedGraphNodeId);
  const selectGraphNode = useMemoryStore((s) => s.selectGraphNode);
  const setViewport = useMemoryStore((s) => s.setViewport);
  const setPan = useMemoryStore((s) => s.setPan);
  const setZoom = useMemoryStore((s) => s.setZoom);

  /**
   * The map actually drawn. When a memory is in view, the workspace asks a
   * narrower question — "what does *this* touch" — so the map is cut down to its
   * neighbourhood and re-laid out, because a subgraph in the full map's
   * positions would be mostly empty space.
   */
  const view = useMemo(() => {
    if (focusMemoryId === null) return graph;
    const anchor = graph.nodes.find((n) => n.memoryId === focusMemoryId);
    if (!anchor) return graph;
    return layoutGraph(neighbourhood(graph, anchor.id));
  }, [graph, focusMemoryId]);

  /**
   * The node standing for the memory in view, if there is one.
   *
   * The `null` guard is load-bearing: a node that isn't a memory carries
   * `memoryId: null`, so matching on `memoryId === focusMemoryId` without it
   * would match the first collection in the graph the moment nothing is focused.
   */
  const focusNodeId = useMemo(() => {
    if (focusMemoryId === null) return null;
    return view.nodes.find((n) => n.memoryId === focusMemoryId)?.id ?? null;
  }, [view.nodes, focusMemoryId]);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;

    const measure = () => setViewport({ width: frame.clientWidth, height: frame.clientHeight });
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(frame);
    return () => observer.disconnect();
  }, [setViewport]);

  const nodeIndex = useMemo(() => new Map(view.nodes.map((n) => [n.id, n])), [view.nodes]);

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

  if (view.nodes.length === 0) {
    return (
      <div className={cn("flex min-h-64 items-center justify-center rounded-lg border bg-card", className)}>
        <EmptyState
          icon={Share2}
          title="Nothing connected yet"
          description="Relationships between memories, employees and workflows will be drawn here."
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
            <KnowledgeGraphMarkers />
            {view.edges.map((edge) => {
              const from = nodeIndex.get(edge.sourceNode);
              const to = nodeIndex.get(edge.targetNode);
              if (!from || !to) return null;
              return (
                <KnowledgeGraphEdge
                  key={edge.id}
                  from={from}
                  to={to}
                  edge={edge}
                  isActive={isEdgeTouching(edge, selectedGraphNodeId)}
                  showLabel={showLabels}
                />
              );
            })}
          </svg>

          {view.nodes.map((node) => (
            <KnowledgeGraphNode
              key={node.id}
              node={node}
              isSelected={selectedGraphNodeId === node.id}
              isFocus={focusNodeId === node.id}
              onSelect={selectGraphNode}
            />
          ))}
        </div>
      </div>

      <GraphControls graph={view} />
    </div>
  );
}
