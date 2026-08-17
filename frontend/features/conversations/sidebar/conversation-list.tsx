"use client";

import { Filter, MessagesSquare, Search } from "lucide-react";
import type { ConversationSummary } from "@/services/conversations";
import { CONVERSATION_STATUSES, CONVERSATION_STATUS_LABEL, CONVERSATION_TAGS, EMPLOYEE_LIST } from "@/services/conversations";
import {
  CONVERSATION_SORTS,
  CONVERSATION_SORT_LABEL,
  hasActiveConversationFilters,
  useConversationStore,
} from "@/store/conversations";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useFilteredConversations } from "../hooks/use-filtered-conversations";
import { ConversationListItem } from "./conversation-list-item";
import { cn } from "@/lib/utils";

export interface ConversationListProps {
  conversations: ConversationSummary[] | undefined;
  onSelect: (id: string) => void;
  className?: string;
}

/**
 * The sidebar: search, filter, sort, and the conversation rows. Filters live
 * in the conversation store, so the same narrowing follows the user from the
 * workspace to history and back.
 */
export function ConversationList({ conversations, onSelect, className }: ConversationListProps) {
  const filters = useConversationStore((s) => s.filters);
  const sort = useConversationStore((s) => s.sort);
  const selectedId = useConversationStore((s) => s.selectedConversationId);
  const setSearch = useConversationStore((s) => s.setSearch);
  const setStatusFilter = useConversationStore((s) => s.setStatusFilter);
  const setEmployeeFilter = useConversationStore((s) => s.setEmployeeFilter);
  const setTagFilter = useConversationStore((s) => s.setTagFilter);
  const setUnreadOnly = useConversationStore((s) => s.setUnreadOnly);
  const setPinnedOnly = useConversationStore((s) => s.setPinnedOnly);
  const resetFilters = useConversationStore((s) => s.resetFilters);
  const setSort = useConversationStore((s) => s.setSort);

  const rows = useFilteredConversations(conversations, filters, sort);
  const hasFilters = hasActiveConversationFilters(filters);

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <div className="space-y-2 border-b p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            type="search"
            value={filters.search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations…"
            aria-label="Search conversations"
            className="h-9 pl-9"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="sr-only" htmlFor="conv-filter-status">
            Status
          </label>
          <Select
            id="conv-filter-status"
            value={filters.status}
            onChange={(e) => setStatusFilter(e.target.value as typeof filters.status)}
            className="h-9 text-xs"
          >
            <option value="ALL">All statuses</option>
            {CONVERSATION_STATUSES.map((status) => (
              <option key={status} value={status}>
                {CONVERSATION_STATUS_LABEL[status]}
              </option>
            ))}
          </Select>

          <label className="sr-only" htmlFor="conv-filter-employee">
            AI employee
          </label>
          <Select
            id="conv-filter-employee"
            value={filters.employeeId}
            onChange={(e) => setEmployeeFilter(e.target.value)}
            className="h-9 text-xs"
          >
            <option value="ALL">All employees</option>
            {EMPLOYEE_LIST.map((employee) => (
              <option key={employee.employeeId} value={employee.employeeId}>
                {employee.employeeName}
              </option>
            ))}
          </Select>

          <label className="sr-only" htmlFor="conv-filter-tag">
            Tag
          </label>
          <Select
            id="conv-filter-tag"
            value={filters.tag}
            onChange={(e) => setTagFilter(e.target.value)}
            className="h-9 text-xs"
          >
            <option value="ALL">All tags</option>
            {CONVERSATION_TAGS.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </Select>

          <label className="sr-only" htmlFor="conv-sort">
            Sort
          </label>
          <Select
            id="conv-sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as typeof sort)}
            className="h-9 text-xs"
          >
            {CONVERSATION_SORTS.map((value) => (
              <option key={value} value={value}>
                {CONVERSATION_SORT_LABEL[value]}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <label className="flex cursor-pointer items-center gap-1.5" htmlFor="conv-unread-only">
              <Checkbox
                id="conv-unread-only"
                checked={filters.unreadOnly}
                onChange={(e) => setUnreadOnly(e.target.checked)}
              />
              Unread
            </label>
            <label className="flex cursor-pointer items-center gap-1.5" htmlFor="conv-pinned-only">
              <Checkbox
                id="conv-pinned-only"
                checked={filters.pinnedOnly}
                onChange={(e) => setPinnedOnly(e.target.checked)}
              />
              Pinned
            </label>
          </div>
          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={resetFilters} className="h-7 px-2 text-xs">
              <Filter className="size-3" aria-hidden="true" />
              Clear
            </Button>
          ) : null}
        </div>
      </div>

      <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto p-2">
        {rows.length === 0 ? (
          <EmptyState
            compact
            icon={MessagesSquare}
            title={hasFilters ? "No conversations match" : "No conversations yet"}
            description={
              hasFilters ? "Try a different word, or clear the filters." : "Start one from the toolbar above."
            }
          />
        ) : (
          <ul className="flex flex-col gap-1">
            {rows.map((conversation) => (
              <li key={conversation.id}>
                <ConversationListItem
                  conversation={conversation}
                  isSelected={selectedId === conversation.id}
                  onSelect={onSelect}
                />
              </li>
            ))}
          </ul>
        )}
      </nav>
    </div>
  );
}
