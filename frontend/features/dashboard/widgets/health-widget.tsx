"use client";

import { memo } from "react";
import { Activity } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { WidgetShell } from "../components/widget-shell";
import { HEALTH_SUBSYSTEM_LABEL } from "../models/health";
import { useHealth } from "../hooks/use-dashboard";

/**
 * Platform Health — readiness per backend subsystem, in the backend's own
 * vocabulary and nothing more. No uptime, no latency, no counters: the platform
 * reports a state per subsystem and this widget shows it. With no backend wired,
 * every subsystem is honestly Unknown.
 */
export const HealthWidget = memo(function HealthWidget() {
  const query = useHealth();
  const health = query.data;

  return (
    <WidgetShell
      title="Platform health"
      description="Readiness of each platform subsystem."
      isLoading={query.isPending}
      isError={query.isError}
      isEmpty={!health || health.subsystems.length === 0}
      isRefreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
      action={health ? <StatusBadge kind="health" status={health.state} /> : null}
      empty={
        <EmptyState
          compact
          icon={Activity}
          title="No readiness reported"
          description="Subsystem readiness appears here once the platform reports in."
        />
      }
    >
      {health ? (
        <>
          <ul aria-label="Subsystem readiness" className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            {health.subsystems.map((subsystem) => (
              <li key={subsystem.subsystem} className="flex items-center justify-between gap-2 py-1">
                <span className="truncate text-sm text-foreground">
                  {HEALTH_SUBSYSTEM_LABEL[subsystem.subsystem]}
                </span>
                <StatusBadge kind="health" status={subsystem.state} />
              </li>
            ))}
          </ul>
          <p className="mt-4 border-t pt-3 text-xs text-muted-foreground">
            {health.state === "UNKNOWN"
              ? "Readiness is unknown until the platform reports in."
              : `${health.healthySubsystems} of ${health.totalSubsystems} subsystems healthy.`}
          </p>
        </>
      ) : null}
    </WidgetShell>
  );
});
