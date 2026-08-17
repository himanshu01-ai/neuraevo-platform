import type { GrowthPoint } from "@/services/memory";
import { formatDate } from "@/utils/format";
import { cn } from "@/lib/utils";

export interface GrowthChartProps {
  points: readonly GrowthPoint[];
  className?: string;
}

/** Viewbox units. The SVG scales to its container; these are just the maths. */
const WIDTH = 600;
const HEIGHT = 160;
const PADDING = 8;

/**
 * Knowledge growth: the running total of memories over time.
 *
 * A hand-drawn SVG line rather than a charting library. It's one path and one
 * fill; a dependency would cost more bytes than the whole workspace to draw it,
 * and would arrive with a palette that isn't this one. Both the stroke and the
 * fill are token classes (`stroke-primary`, `fill-primary`), so it themes with
 * everything else and has no colour of its own.
 *
 * The plotting is a pure function of the points, so it renders identically on
 * the server and the client — no measurement, no refs, no effects, nothing to
 * mismatch on hydration.
 *
 * Accessibility: the drawing is decorative, and the same series is published
 * underneath as a real table that a screen reader can read row by row. A line
 * nobody can hear is not a chart, it's a decoration.
 */
export function GrowthChart({ points, className }: GrowthChartProps) {
  if (points.length === 0) {
    return <p className={cn("text-sm text-muted-foreground", className)}>Nothing stored yet.</p>;
  }

  const maxTotal = points.reduce((max, p) => Math.max(max, p.total), 0) || 1;
  const step = points.length > 1 ? (WIDTH - PADDING * 2) / (points.length - 1) : 0;

  const coords = points.map((point, index) => ({
    x: PADDING + index * step,
    // SVG y grows downward, so a bigger total sits higher up.
    y: PADDING + (1 - point.total / maxTotal) * (HEIGHT - PADDING * 2),
    point,
  }));

  const line = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(2)} ${c.y.toFixed(2)}`).join(" ");
  const first = coords[0];
  const last = coords[coords.length - 1];
  const area =
    first && last
      ? `${line} L ${last.x.toFixed(2)} ${HEIGHT - PADDING} L ${first.x.toFixed(2)} ${HEIGHT - PADDING} Z`
      : "";

  return (
    <figure className={cn("space-y-2", className)}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        role="presentation"
        aria-hidden="true"
        className="h-40 w-full"
      >
        <path d={area} className="fill-primary/10" />
        <path
          d={line}
          fill="none"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="stroke-primary"
          // preserveAspectRatio="none" stretches the stroke with the box; this
          // keeps the line an even 2px whatever the container's aspect is.
          vectorEffect="non-scaling-stroke"
        />
        {last ? <circle cx={last.x} cy={last.y} r={3} className="fill-primary" /> : null}
      </svg>

      <figcaption className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{first ? formatDate(first.point.day) : ""}</span>
        <span>
          <span className="font-medium tabular-nums text-foreground">{last?.point.total ?? 0}</span> total
        </span>
        <span>{last ? formatDate(last.point.day) : ""}</span>
      </figcaption>

      {/* The chart, in a form that can actually be read out. */}
      <details className="text-xs">
        <summary className="cursor-pointer rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          Growth as a table
        </summary>
        <div className="mt-2 max-h-40 overflow-y-auto">
          <table className="w-full text-left">
            <caption className="sr-only">Running total of memories by the day they were stored</caption>
            <thead>
              <tr className="text-muted-foreground">
                <th scope="col" className="py-1 font-medium">
                  Day
                </th>
                <th scope="col" className="py-1 text-right font-medium">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.day} className="border-t">
                  <td className="py-1 text-foreground">
                    <time dateTime={point.day}>{formatDate(point.day)}</time>
                  </td>
                  <td className="py-1 text-right tabular-nums text-foreground">{point.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
