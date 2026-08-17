"use client";

import { useMemo } from "react";
import type { NotificationSummary } from "@/services/collaboration";
import type { NotificationFilters } from "@/services/collaboration";
import { dateValue, isoDay } from "@/utils/format";

/**
 * Applies the toolbar's filters to the notification feed. Pure and memoized —
 * the feed recomputes only when its inputs change, so an unrelated re-render
 * never re-sorts it.
 *
 * Archived notifications are excluded here: the center and inbox show live
 * items, and the archive is reached through the archived filter's own view.
 * Pinned notifications lead in every ordering — a pin is the user saying "keep
 * this on top", and no sort outranks the user.
 */
export function useFilteredNotifications(
  rows: NotificationSummary[] | undefined,
  filters: NotificationFilters,
  options?: { includeArchived?: boolean }
): NotificationSummary[] {
  const includeArchived = options?.includeArchived ?? false;

  return useMemo(() => {
    if (!rows) return [];
    const term = filters.search.trim().toLowerCase();

    const filtered = rows.filter((row) => {
      if (!includeArchived && row.archived) return false;
      if (filters.unreadOnly && row.read) return false;
      if (filters.type !== "ALL" && row.type !== filters.type) return false;
      if (filters.priority !== "ALL" && row.priority !== filters.priority) return false;
      if (filters.source !== "ALL" && row.primaryEntity?.kind !== filters.source) return false;

      const day = isoDay(row.createdAt);
      if (filters.fromDate && day < filters.fromDate) return false;
      if (filters.toDate && day > filters.toDate) return false;

      if (!term) return true;
      return [row.title, row.description, row.source.name].join(" ").toLowerCase().includes(term);
    });

    return filtered.sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return dateValue(b.createdAt) - dateValue(a.createdAt);
    });
  }, [rows, filters, includeArchived]);
}
