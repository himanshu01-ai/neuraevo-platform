"use client";

import { useCallback, useEffect, useState, type PointerEvent as ReactPointerEvent, type RefObject } from "react";
import { snapPosition, type CanvasPosition } from "@/services/workflows";
import { useBuilderStore } from "@/store/workflow";

/**
 * Pointer handling for the canvas: dragging a node, panning the surface, and
 * drawing a connection.
 *
 * Listeners go on `window` rather than the element, so a drag keeps tracking
 * when the pointer leaves the canvas and always ends — even on a pointercancel.
 * The store is read through `getState()` inside the listeners so a long-lived
 * drag never closes over a stale zoom or pan.
 */

type Interaction =
  | { mode: "node"; nodeId: string; grabOffset: CanvasPosition }
  | { mode: "pan"; pointerOrigin: CanvasPosition; panOrigin: CanvasPosition }
  | { mode: "connect" };

/** The node under a screen point, via its `data-node-id` marker. */
function nodeIdAtPoint(clientX: number, clientY: number): string | null {
  const element = document.elementFromPoint(clientX, clientY);
  const host = element?.closest("[data-node-id]");
  return host?.getAttribute("data-node-id") ?? null;
}

export function useCanvasInteraction(surfaceRef: RefObject<HTMLDivElement | null>) {
  const [interaction, setInteraction] = useState<Interaction | null>(null);

  /** Screen coordinates → canvas coordinates, undoing pan and zoom. */
  const toCanvas = useCallback(
    (clientX: number, clientY: number): CanvasPosition => {
      const rect = surfaceRef.current?.getBoundingClientRect();
      const { pan, zoom } = useBuilderStore.getState();
      return {
        x: (clientX - (rect?.left ?? 0) - pan.x) / zoom,
        y: (clientY - (rect?.top ?? 0) - pan.y) / zoom,
      };
    },
    [surfaceRef]
  );

  const startNodeDrag = useCallback(
    (event: ReactPointerEvent, nodeId: string) => {
      if (event.button !== 0) return;
      event.stopPropagation();
      const store = useBuilderStore.getState();
      const node = store.graph.nodes.find((n) => n.id === nodeId);
      if (!node) return;

      const pointer = toCanvas(event.clientX, event.clientY);
      store.selectNode(nodeId);
      store.beginNodeDrag();
      setInteraction({
        mode: "node",
        nodeId,
        grabOffset: { x: pointer.x - node.position.x, y: pointer.y - node.position.y },
      });
    },
    [toCanvas]
  );

  const startPan = useCallback((event: ReactPointerEvent) => {
    if (event.button !== 0) return;
    const { pan } = useBuilderStore.getState();
    setInteraction({
      mode: "pan",
      pointerOrigin: { x: event.clientX, y: event.clientY },
      panOrigin: pan,
    });
  }, []);

  const startConnect = useCallback(
    (event: ReactPointerEvent, sourceNode: string) => {
      if (event.button !== 0) return;
      event.stopPropagation();
      useBuilderStore.getState().startConnect(sourceNode, toCanvas(event.clientX, event.clientY));
      setInteraction({ mode: "connect" });
    },
    [toCanvas]
  );

  useEffect(() => {
    if (!interaction) return;

    const handleMove = (event: PointerEvent) => {
      const store = useBuilderStore.getState();

      if (interaction.mode === "node") {
        const pointer = toCanvas(event.clientX, event.clientY);
        // Snap while dragging: the grid is the point, and a node that settles
        // only on release reads as drift.
        store.moveNode(
          interaction.nodeId,
          snapPosition({
            x: pointer.x - interaction.grabOffset.x,
            y: pointer.y - interaction.grabOffset.y,
          })
        );
        return;
      }

      if (interaction.mode === "pan") {
        store.setPan({
          x: interaction.panOrigin.x + (event.clientX - interaction.pointerOrigin.x),
          y: interaction.panOrigin.y + (event.clientY - interaction.pointerOrigin.y),
        });
        return;
      }

      store.updateConnect(toCanvas(event.clientX, event.clientY));
    };

    const handleUp = (event: PointerEvent) => {
      const store = useBuilderStore.getState();
      if (interaction.mode === "node") store.endNodeDrag(interaction.nodeId);
      if (interaction.mode === "connect") store.endConnect(nodeIdAtPoint(event.clientX, event.clientY));
      setInteraction(null);
    };

    const handleCancel = () => {
      const store = useBuilderStore.getState();
      if (interaction.mode === "connect") store.endConnect(null);
      setInteraction(null);
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("pointercancel", handleCancel);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("pointercancel", handleCancel);
    };
  }, [interaction, toCanvas]);

  return {
    startNodeDrag,
    startPan,
    startConnect,
    isPanning: interaction?.mode === "pan",
    isDraggingNode: interaction?.mode === "node",
  };
}
