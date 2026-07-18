import { memo } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import type { OverviewMetric } from "@/services/dashboard";
import { OVERVIEW_CARD_META } from "../models/overview";
import { TrendIndicator } from "./trend-indicator";

/**
 * One overview card: icon, title, value, status, secondary text, and the trend
 * placeholder. Every number is carried in from the service — the card computes
 * nothing. A metric the platform can't report yet shows an em dash rather than a
 * zero, because "unknown" and "none" are different answers.
 *
 * Memoized like every other card rendered in a list, so a widget refresh only
 * repaints the metrics that actually changed.
 */
export const MetricCard = memo(function MetricCard({ metric }: { metric: OverviewMetric }) {
  const meta = OVERVIEW_CARD_META[metric.id];
  const Icon = meta.icon;
  const hasValue = metric.value !== null;

  return (
    <Link
      href={meta.href}
      className="group block rounded-lg border bg-card p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary transition-colors group-hover:bg-primary/15">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <Badge variant={TONE_VARIANT[metric.status.tone]}>{metric.status.label}</Badge>
      </div>

      <h3 className="mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">{meta.title}</h3>

      <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
        <span aria-hidden="true">{hasValue ? metric.value : "—"}</span>
        <span className="sr-only">{hasValue ? `${metric.value} ${meta.unit}` : `${meta.unit} not reported`}</span>
      </p>

      <p className="mt-1 text-xs text-muted-foreground">{metric.secondary}</p>
      <TrendIndicator trend={metric.trend} className="mt-3" />
    </Link>
  );
});
