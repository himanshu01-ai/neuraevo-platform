"use client";

import { useMemo } from "react";
import type { ConversationSummary } from "@/services/conversations";
import type { ConversationFilters, ConversationSort } from "@/store/conversations";
import { dateValue } from "@/utils/format";

/**
 * Applies the sidebar's filters and sort to the conversation list. Pure and
 * memoized — the list recomputes only when the inputs change, so typing in the
 * composer never re-sorts the sidebar.
 *
 * Pinned conversations lead in every ordering: a pin is the user saying "keep
 * this on top", and no sort outranks the user.
 */
export function useFilteredConversations(
  rows: ConversationSummary[] | undefined,
  filters: ConversationFilters,
  sort: ConversationSort
): ConversationSummary[] {
  return useMemo(() => {
    if (!rows) return [];
    const term = filters.search.trim().toLowerCase();

    const filtered = rows.filter((row) => {
      if (filters.status !== "ALL" && row.status !== filters.status) return false;
      if (filters.employeeId !== "ALL" && row.employee.employeeId !== filters.employeeId) return false;
      if (filters.tag !== "ALL" && !row.tags.includes(filters.tag)) return false;
      if (filters.unreadOnly && row.unreadCount === 0) return false;
      if (filters.pinnedOnly && !row.pinned) return false;
      if (!term) return true;
      return [row.title, row.employee.employeeName, row.lastMessagePreview, row.tags.join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });

    const byRecent = (a: ConversationSummary, b: ConversationSummary) =>
      dateValue(b.updatedAt) - dateValue(a.updatedAt);

    return filtered.sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      switch (sort) {
        case "name":
          return a.title.localeCompare(b.title);
        case "unread":
          return b.unreadCount - a.unreadCount || byRecent(a, b);
        case "recent":
          return byRecent(a, b);
      }
    });
  }, [rows, filters, sort]);
}
