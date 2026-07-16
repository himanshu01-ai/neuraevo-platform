"use client";

import { useMemo } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { dashboardKeys, dashboardService, type WorkspaceSignals } from "@/services/dashboard";
import { selectSuggestions, type SuggestionRule } from "../models/suggestions";

/**
 * One query hook per widget. Each wraps `services/dashboard`, so a widget never
 * knows whether its data came from a mock adapter or a backend — and each gets
 * loading, error, and `refetch` (the refresh action) from the query itself.
 *
 * `staleTime` follows docs/09: readiness is the liveliest surface, stored
 * content the least.
 */
const STALE_TIME = 60_000;
const HEALTH_STALE_TIME = 15_000;
const MEMORY_STALE_TIME = 300_000;

export function useOverview() {
  return useQuery({
    queryKey: dashboardKeys.overview,
    queryFn: dashboardService.overview,
    staleTime: STALE_TIME,
  });
}

export function useRecentTasks() {
  return useQuery({
    queryKey: dashboardKeys.tasks,
    queryFn: dashboardService.recentTasks,
    staleTime: STALE_TIME,
  });
}

export function useRecentWorkflows() {
  return useQuery({
    queryKey: dashboardKeys.workflows,
    queryFn: dashboardService.recentWorkflows,
    staleTime: STALE_TIME,
  });
}

export function useActiveEmployees() {
  return useQuery({
    queryKey: dashboardKeys.employees,
    queryFn: dashboardService.activeEmployees,
    staleTime: STALE_TIME,
  });
}

export function usePendingApprovals() {
  return useQuery({
    queryKey: dashboardKeys.approvals,
    queryFn: dashboardService.pendingApprovals,
    staleTime: STALE_TIME,
  });
}

export function useMemorySummary() {
  return useQuery({
    queryKey: dashboardKeys.memory,
    queryFn: dashboardService.memorySummary,
    staleTime: MEMORY_STALE_TIME,
  });
}

export function useRecentNotifications() {
  return useQuery({
    queryKey: dashboardKeys.notifications,
    queryFn: dashboardService.recentNotifications,
    staleTime: STALE_TIME,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: dashboardKeys.health,
    queryFn: dashboardService.health,
    staleTime: HEALTH_STALE_TIME,
  });
}

export interface SuggestionsResult {
  query: UseQueryResult<WorkspaceSignals>;
  suggestions: SuggestionRule[];
}

/** Signals come from the service; the rules that read them are pure and local. */
export function useSuggestions(limit = 3): SuggestionsResult {
  const query = useQuery({
    queryKey: dashboardKeys.signals,
    queryFn: dashboardService.workspaceSignals,
    staleTime: STALE_TIME,
  });

  const suggestions = useMemo(
    () => (query.data ? selectSuggestions(query.data, limit) : []),
    [query.data, limit]
  );

  return { query, suggestions };
}
