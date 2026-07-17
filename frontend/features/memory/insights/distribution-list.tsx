import type { DistributionSlice } from "@/services/memory";
import { Progress } from "@/components/ui/progress";
import { formatPercent } from "@/utils/format";
import { cn } from "@/lib/utils";

export interface DistributionListProps {
  slices: readonly DistributionSlice[];
  /** Said when there's nothing to chart. */
  emptyLabel?: string;
  className?: string;
}

/**
 * A distribution as labelled proportion bars.
 *
 * This is a chart built from <Progress> rather than a new charting primitive.
 * Every distribution this workspace shows is "a label, a count, and its share of
 * the whole", and that is exactly what a labelled bar says — reaching for a
 * charting library, or inventing a Chart component, would add a dependency and a
 * palette to draw the same rectangle the design system already ships.
 *
 * It reads as a definition list because that's what it is: a term and its value.
 * The bar is decorative reinforcement; the number is always there in text, so
 * the data survives without colour, without CSS, and in a screen reader.
 */
export function DistributionList({
  slices,
  emptyLabel = "Nothing to show yet.",
  className,
}: DistributionListProps) {
  if (slices.length === 0) {
    return <p className={cn("text-sm text-muted-foreground", className)}>{emptyLabel}</p>;
  }

  return (
    <dl className={cn("space-y-2.5", className)}>
      {slices.map((entry) => (
        <div key={entry.label}>
          <div className="flex items-center justify-between gap-2 text-sm">
            <dt className="min-w-0 truncate text-foreground">{entry.label}</dt>
            <dd className="shrink-0 tabular-nums text-muted-foreground">
              {entry.count}
              <span className="ml-1.5 text-xs">{formatPercent(entry.ratio)}</span>
            </dd>
          </div>
          <Progress
            value={entry.ratio * 100}
            label={`${entry.label}: ${entry.count}, ${formatPercent(entry.ratio)} of the total`}
            className="mt-1.5"
          />
        </div>
      ))}
    </dl>
  );
}
