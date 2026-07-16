"use client";

import { NODE_HEIGHT, NODE_WIDTH, graphBounds } from "@/services/workflows";
import { useBuilderStore } from "@/store/workflow";

const MAP_WIDTH = 160;
const MAP_HEIGHT = 100;
const MAP_PADDING = 40;

/**
 * Overview of the whole graph with the current viewport outlined.
 *
 * Read-only: it reflects the canvas but doesn't drive it, and it's hidden from
 * assistive tech because it conveys nothing the node list doesn't already say
 * better. Click-to-navigate is a natural next step.
 */
export function CanvasMinimap() {
  const nodes = useBuilderStore((s) => s.graph.nodes);
  const pan = useBuilderStore((s) => s.pan);
  const zoom = useBuilderStore((s) => s.zoom);
  const viewport = useBuilderStore((s) => s.viewport);

  const bounds = graphBounds(nodes);
  if (!bounds) return null;

  const width = bounds.maxX - bounds.minX + MAP_PADDING * 2;
  const height = bounds.maxY - bounds.minY + MAP_PADDING * 2;
  const scale = Math.min(MAP_WIDTH / width, MAP_HEIGHT / height);
  const originX = bounds.minX - MAP_PADDING;
  const originY = bounds.minY - MAP_PADDING;

  // The visible region, expressed back in canvas coordinates.
  const viewX = -pan.x / zoom;
  const viewY = -pan.y / zoom;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute bottom-4 right-4 hidden rounded-md border bg-card/95 p-1 shadow-md md:block"
    >
      <svg width={MAP_WIDTH} height={MAP_HEIGHT} className="overflow-hidden rounded-sm">
        {nodes.map((node) => (
          <rect
            key={node.id}
            x={(node.position.x - originX) * scale}
            y={(node.position.y - originY) * scale}
            width={NODE_WIDTH * scale}
            height={NODE_HEIGHT * scale}
            rx={1}
            className="fill-muted-foreground/50"
          />
        ))}
        <rect
          x={(viewX - originX) * scale}
          y={(viewY - originY) * scale}
          width={(viewport.width / zoom) * scale}
          height={(viewport.height / zoom) * scale}
          className="fill-primary/10 stroke-primary"
          strokeWidth={1}
        />
      </svg>
    </div>
  );
}
