"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { History, Pin, Search, Users } from "lucide-react";
import type { ConversationStatus, ConversationSummary } from "@/services/conversations";
import {
  CONVERSATION_STATUSES,
  CONVERSATION_STATUS_LABEL,
  CONVERSATION_STATUS_TONE,
} from "@/services/conversations";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { Select } from "@/components/ui/select";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { formatDateTime } from "@/utils/format";
import { useConversationList } from "../hooks/use-conversations";
import { dateValue } from "@/utils/format";

export interface ConversationHistoryProps {
  /** Narrows the record to conversations shared with teammates. */
  sharedOnly?: boolean;
}

/**
 * The record of every conversation, newest activity first — each row linking
 * into the workspace with that thread open. With `sharedOnly`, the same
 * screen reads as the shared-conversations view; one component, because they
 * are one question with one facet changed.
 */
export function ConversationHistory({ sharedOnly = false }: ConversationHistoryProps) {
  const list = useConversationList();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ConversationStatus | "ALL">("ALL");

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (list.data ?? [])
      .filter((row) => {
        if (sharedOnly && !row.shared) return false;
        if (status !== "ALL" && row.status !== status) return false;
        if (!term) return true;
        return [row.title, row.employee.employeeName, row.tags.join(" ")].join(" ").toLowerCase().includes(term);
      })
      .sort((a, b) => dateValue(b.updatedAt) - dateValue(a.updatedAt));
  }, [list.data, search, status, sharedOnly]);

  if (list.isError) {
    return (
      <ErrorState
        title="Couldn't load conversations"
        description="The record couldn't be loaded. Try again in a moment."
        onRetry={() => void list.refetch()}
      />
    );
  }

  if (list.isPending) return <LoadingState rows={5} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by title, employee, or tag…"
            aria-label="Search conversation history"
            className="pl-9"
          />
        </div>
        <label className="sr-only" htmlFor="history-status">
          Status
        </label>
        <Select
          id="history-status"
          value={status}
          onChange={(e) => setStatus(e.target.value as ConversationStatus | "ALL")}
          className="sm:w-44"
        >
          <option value="ALL">All statuses</option>
          {CONVERSATION_STATUSES.map((value) => (
            <option key={value} value={value}>
              {CONVERSATION_STATUS_LABEL[value]}
            </option>
          ))}
        </Select>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          icon={sharedOnly ? Users : History}
          title={sharedOnly ? "Nothing shared yet" : "No conversations match"}
          description={
            sharedOnly
              ? "Share a conversation from the workspace toolbar and it will appear here for teammates."
              : "Try a different word, or clear the status filter."
          }
        />
      ) : (
        <ul className="flex flex-col gap-2" aria-label={sharedOnly ? "Shared conversations" : "Conversation history"}>
          {rows.map((row) => (
            <li key={row.id}>
              <HistoryRow row={row} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function HistoryRow({ row }: { row: ConversationSummary }) {
  return (
    <Link
      href={`/workspace/conversations/${row.id}`}
      className="flex items-center gap-3 rounded-lg border bg-card p-3 shadow-sm transition-all hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Avatar name={row.employee.employeeName} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="truncate text-sm font-medium text-foreground">{row.title}</span>
          {row.pinned ? <Pin className="size-3 shrink-0 text-primary" aria-label="Pinned" /> : null}
          {row.shared ? <Users className="size-3 shrink-0 text-muted-foreground" aria-label="Shared" /> : null}
          {row.unreadCount > 0 ? (
            <Badge variant="primary" className="px-1.5 py-0 text-[0.65rem]">
              {row.unreadCount} unread
            </Badge>
          ) : null}
        </span>
        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
          {row.employee.employeeName} · {row.lastMessagePreview}
        </span>
      </span>
      <span className="hidden shrink-0 flex-col items-end gap-1 sm:flex">
        <Badge variant={TONE_VARIANT[CONVERSATION_STATUS_TONE[row.status]]}>
          {CONVERSATION_STATUS_LABEL[row.status]}
        </Badge>
        <time dateTime={row.updatedAt} className="text-xs text-muted-foreground">
          {formatDateTime(row.updatedAt)}
        </time>
      </span>
    </Link>
  );
}
