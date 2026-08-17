"use client";

import { Filter, Search } from "lucide-react";
import {
  NOTIFICATION_TYPES,
  NOTIFICATION_TYPE_LABEL,
} from "@/services/collaboration";
import { ENTITY_META } from "../models/notification-meta";
import { PRIORITY_LABEL } from "@/types/domain";
import type { Priority } from "@/types/domain";
import {
  hasActiveNotificationFilters,
  useCollaborationStore,
  type NotificationViewMode,
} from "@/store/collaboration";
import type { EntityKind, NotificationType } from "@/services/collaboration";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const PRIORITIES: Priority[] = ["URGENT", "HIGH", "MEDIUM", "LOW"];
const SOURCES: EntityKind[] = ["task", "workflow", "memory", "conversation", "employee"];
const VIEW_MODES: { value: NotificationViewMode; label: string }[] = [
  { value: "comfortable", label: "Comfortable" },
  { value: "compact", label: "Compact" },
];

/**
 * The filter bar over a feed: search, unread, type, priority, source, and a
 * date range — every facet reading from the collaboration store, so the same
 * narrowing follows the user between the center's tabs. View mode rides here
 * too; it's the one durable preference.
 */
export function NotificationFilterBar({ className }: { className?: string }) {
  const filters = useCollaborationStore((s) => s.filters);
  const viewMode = useCollaborationStore((s) => s.viewMode);
  const setSearch = useCollaborationStore((s) => s.setSearch);
  const setUnreadOnly = useCollaborationStore((s) => s.setUnreadOnly);
  const setTypeFilter = useCollaborationStore((s) => s.setTypeFilter);
  const setPriorityFilter = useCollaborationStore((s) => s.setPriorityFilter);
  const setSourceFilter = useCollaborationStore((s) => s.setSourceFilter);
  const setFromDate = useCollaborationStore((s) => s.setFromDate);
  const setToDate = useCollaborationStore((s) => s.setToDate);
  const resetFilters = useCollaborationStore((s) => s.resetFilters);
  const setViewMode = useCollaborationStore((s) => s.setViewMode);

  const active = hasActiveNotificationFilters(filters);

  return (
    <div className={cn("space-y-2 rounded-lg border bg-card p-3 shadow-sm", className)}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            type="search"
            value={filters.search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search notifications…"
            aria-label="Search notifications"
            className="h-9 pl-9"
          />
        </div>

        <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-sm text-muted-foreground" htmlFor="ntf-unread">
          <input
            id="ntf-unread"
            type="checkbox"
            checked={filters.unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="size-4 shrink-0 cursor-pointer rounded border-input accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          />
          Unread only
        </label>

        <label className="sr-only" htmlFor="ntf-view">
          View density
        </label>
        <Select
          id="ntf-view"
          value={viewMode}
          onChange={(e) => setViewMode(e.target.value as NotificationViewMode)}
          className="h-9 sm:w-40"
        >
          {VIEW_MODES.map((mode) => (
            <option key={mode.value} value={mode.value}>
              {mode.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <div>
          <label className="sr-only" htmlFor="ntf-type">
            Type
          </label>
          <Select
            id="ntf-type"
            value={filters.type}
            onChange={(e) => setTypeFilter(e.target.value as NotificationType | "ALL")}
            className="h-9 text-xs"
          >
            <option value="ALL">All types</option>
            {NOTIFICATION_TYPES.map((type) => (
              <option key={type} value={type}>
                {NOTIFICATION_TYPE_LABEL[type]}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <label className="sr-only" htmlFor="ntf-priority">
            Priority
          </label>
          <Select
            id="ntf-priority"
            value={filters.priority}
            onChange={(e) => setPriorityFilter(e.target.value as Priority | "ALL")}
            className="h-9 text-xs"
          >
            <option value="ALL">All priorities</option>
            {PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {PRIORITY_LABEL[priority]}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <label className="sr-only" htmlFor="ntf-source">
            Source
          </label>
          <Select
            id="ntf-source"
            value={filters.source}
            onChange={(e) => setSourceFilter(e.target.value as EntityKind | "ALL")}
            className="h-9 text-xs"
          >
            <option value="ALL">All sources</option>
            {SOURCES.map((source) => (
              <option key={source} value={source}>
                {ENTITY_META[source].label}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <label className="sr-only" htmlFor="ntf-from">
            From date
          </label>
          <Input
            id="ntf-from"
            type="date"
            value={filters.fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            aria-label="From date"
            className="h-9 text-xs"
          />
        </div>

        <div>
          <label className="sr-only" htmlFor="ntf-to">
            To date
          </label>
          <Input
            id="ntf-to"
            type="date"
            value={filters.toDate}
            onChange={(e) => setToDate(e.target.value)}
            aria-label="To date"
            className="h-9 text-xs"
          />
        </div>
      </div>

      {active ? (
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" onClick={resetFilters} className="h-7 px-2 text-xs">
            <Filter className="size-3" aria-hidden="true" />
            Clear filters
          </Button>
        </div>
      ) : null}
    </div>
  );
}
