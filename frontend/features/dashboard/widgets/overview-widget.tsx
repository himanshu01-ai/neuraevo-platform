"use client";

import { memo } from "react";
import { LayoutDashboard } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { WidgetShell } from "../components/widget-shell";
import { MetricCard } from "../components/metric-card";
import { MetricCardSkeleton } from "../components/widget-skeleton";
import { useOverview } from "../hooks/use-dashboard";

const GRID = "grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6";

/** Today's Overview — the six platform cards. */
export const OverviewWidget = memo(function OverviewWidget() {
  const query = useOverview();
  const metrics = query.data ?? [];

  return (
    <WidgetShell
      variant="bare"
      title="Today's overview"
      description="Where your workspace stands right now."
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={metrics.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      loading={
        <div role="status" aria-label="Loading overview" className={GRID}>
          {Array.from({ length: 6 }).map((_, i) => (
            <MetricCardSkeleton key={i} />
          ))}
        </div>
      }
      empty={
        <EmptyState
          icon={LayoutDashboard}
          title="No overview yet"
          description="Once your workspace has work in it, its numbers appear here."
        />
      }
    >
      <div className={GRID}>
        {metrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} />
        ))}
      </div>
    </WidgetShell>
  );
});
