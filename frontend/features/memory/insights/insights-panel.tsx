"use client";

import { ErrorState } from "@/components/ui/error-state";
import { Shimmer } from "@/components/ui/shimmer";
import { Panel } from "@/features/workspace/panels/panel";
import { formatBytes, formatPercent } from "@/utils/format";
import { useMemoryInsights } from "../hooks/use-memory";
import { MemoryTimeline } from "../timeline/memory-timeline";
import { DistributionList } from "./distribution-list";
import { GrowthChart } from "./growth-chart";
import { cn } from "@/lib/utils";

export interface InsightsPanelProps {
  /** Trims to the essentials where space is tight (the dock). */
  compact?: boolean;
  className?: string;
}

/**
 * What the knowledge looks like as a whole.
 *
 * `totals` is the one section with a real endpoint behind it — it mirrors the
 * frozen `MemoryStatsResponse` field for field, so Sprint 17.9 binds it
 * directly. Everything else is aggregated by the mock from projected fields and
 * needs the backend to grow those columns first.
 *
 * Nothing here is a computed insight in the AI sense: these are counts and
 * shares of counts. No trend is inferred, nothing is predicted, and nothing is
 * ranked by relevance.
 */
export function InsightsPanel({ compact = false, className }: InsightsPanelProps) {
  const query = useMemoryInsights();

  if (query.isPending) {
    return (
      <div role="status" aria-label="Loading insights" className={cn("grid gap-4 lg:grid-cols-2", className)}>
        {Array.from({ length: compact ? 2 : 6 }).map((_, i) => (
          <Shimmer key={i} className="h-48" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        compact
        title="Couldn't load insights"
        description="The knowledge summary couldn't be loaded."
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }

  const insights = query.data;
  const { totals } = insights;

  const stats: { label: string; value: string }[] = [
    { label: "Memories", value: String(totals.totalMemories) },
    { label: "Permanent", value: String(totals.permanentCount) },
    { label: "Working", value: String(totals.workingCount) },
    { label: "Learned", value: String(totals.learnedCount) },
    { label: "Avg. importance", value: formatPercent(totals.averageImportanceScore) },
    { label: "Total size", value: formatBytes(insights.totalSizeBytes) },
  ];

  return (
    <div className={cn("space-y-4", className)}>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-lg border bg-card p-3 shadow-sm">
            <dt className="truncate text-xs text-muted-foreground">{stat.label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">{stat.value}</dd>
          </div>
        ))}
      </dl>

      <div className={cn("grid gap-4", compact ? "lg:grid-cols-2" : "lg:grid-cols-2")}>
        <Panel title="Memory distribution" description="By retention — the platform's own classification.">
          <DistributionList slices={insights.distribution} />
        </Panel>

        <Panel title="Knowledge growth" description="Running total of what's stored.">
          <GrowthChart points={insights.growth} />
        </Panel>

        {!compact ? (
          <>
            <Panel title="Collection usage" description="Where the knowledge is filed.">
              <DistributionList slices={insights.collectionUsage} />
            </Panel>

            <Panel title="Document types" description="What kind of thing each memory is.">
              <DistributionList slices={insights.kinds} />
            </Panel>

            <Panel title="Language distribution" description="What the knowledge is written in.">
              <DistributionList slices={insights.languages} />
            </Panel>

            <Panel title="Top linked employees" description="Who reaches for the most.">
              <DistributionList
                slices={insights.topEmployees}
                emptyLabel="Nothing is linked to an employee yet."
              />
            </Panel>

            <Panel
              title="Recent changes"
              description="The last few things to happen."
              className="lg:col-span-2"
            >
              <MemoryTimeline memoryId={null} limit={6} showMemory />
            </Panel>
          </>
        ) : null}
      </div>
    </div>
  );
}
