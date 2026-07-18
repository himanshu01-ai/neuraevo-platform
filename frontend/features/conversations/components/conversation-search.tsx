"use client";

import Link from "next/link";
import { useState } from "react";
import { SearchX } from "lucide-react";
import {
  CONVERSATION_STATUSES,
  CONVERSATION_STATUS_LABEL,
  CONVERSATION_TAGS,
  EMPLOYEE_LIST,
  EMPTY_SEARCH_QUERY,
  SEARCH_SCOPES,
  SEARCH_SCOPE_LABEL,
  type ConversationSearchQuery,
  type ConversationSearchResult,
} from "@/services/conversations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { Select } from "@/components/ui/select";
import { formatDateTime } from "@/utils/format";
import { useConversationSearch } from "../hooks/use-conversations";

/**
 * Search across the conversation record: keyword, scope (conversations,
 * messages, employees, workflows, tasks, memories), employee, status, tag and
 * date range. The form submits — the adapter is asked once per query, not per
 * keystroke — and every hit deep-links into the workspace with its
 * conversation open.
 */
export function ConversationSearch() {
  const [draft, setDraft] = useState<ConversationSearchQuery>(EMPTY_SEARCH_QUERY);
  const [submitted, setSubmitted] = useState<ConversationSearchQuery | null>(null);

  const results = useConversationSearch(submitted ?? EMPTY_SEARCH_QUERY, submitted !== null);

  const set = <K extends keyof ConversationSearchQuery>(key: K, value: ConversationSearchQuery[K]) =>
    setDraft((q) => ({ ...q, [key]: value }));

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(draft);
        }}
        className="space-y-4 rounded-lg border bg-card p-4 shadow-sm"
        aria-label="Search conversations"
      >
        <Field label="Keyword">
          {({ id }) => (
            <Input
              id={id}
              type="search"
              value={draft.keyword}
              onChange={(e) => set("keyword", e.target.value)}
              placeholder="What was said, referenced, or generated…"
            />
          )}
        </Field>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Scope">
            {({ id }) => (
              <Select
                id={id}
                value={draft.scope}
                onChange={(e) => set("scope", e.target.value as ConversationSearchQuery["scope"])}
              >
                <option value="ALL">Everything</option>
                {SEARCH_SCOPES.map((scope) => (
                  <option key={scope} value={scope}>
                    {SEARCH_SCOPE_LABEL[scope]}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="AI employee">
            {({ id }) => (
              <Select id={id} value={draft.employeeId} onChange={(e) => set("employeeId", e.target.value)}>
                <option value="ALL">All employees</option>
                {EMPLOYEE_LIST.map((employee) => (
                  <option key={employee.employeeId} value={employee.employeeId}>
                    {employee.employeeName}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Status">
            {({ id }) => (
              <Select
                id={id}
                value={draft.status}
                onChange={(e) => set("status", e.target.value as ConversationSearchQuery["status"])}
              >
                <option value="ALL">All statuses</option>
                {CONVERSATION_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {CONVERSATION_STATUS_LABEL[status]}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Tag">
            {({ id }) => (
              <Select id={id} value={draft.tag} onChange={(e) => set("tag", e.target.value)}>
                <option value="ALL">All tags</option>
                {CONVERSATION_TAGS.map((tag) => (
                  <option key={tag} value={tag}>
                    {tag}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="From">
            {({ id }) => (
              <Input id={id} type="date" value={draft.fromDate} onChange={(e) => set("fromDate", e.target.value)} />
            )}
          </Field>

          <Field label="To">
            {({ id }) => (
              <Input id={id} type="date" value={draft.toDate} onChange={(e) => set("toDate", e.target.value)} />
            )}
          </Field>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="submit">Search</Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setDraft(EMPTY_SEARCH_QUERY);
              setSubmitted(null);
            }}
          >
            Clear
          </Button>
        </div>
      </form>

      {submitted === null ? (
        <p className="text-sm text-muted-foreground">
          Search runs across conversations, messages, and everything a thread references.
        </p>
      ) : results.isPending ? (
        <LoadingState rows={4} />
      ) : results.isError ? (
        <ErrorState
          title="Search failed"
          description="That search couldn't be run. Try again in a moment."
          onRetry={() => void results.refetch()}
        />
      ) : results.data.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No matches"
          description="Nothing in the record matches that search. Try a broader scope or fewer facets."
        />
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground" role="status">
            {results.data.length} {results.data.length === 1 ? "match" : "matches"}
          </p>
          <ul className="flex flex-col gap-2" aria-label="Search results">
            {results.data.map((hit) => (
              <li key={hit.id}>
                <SearchHit hit={hit} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SearchHit({ hit }: { hit: ConversationSearchResult }) {
  return (
    <Link
      href={`/workspace/conversations/${hit.conversationId}`}
      className="flex flex-col gap-1 rounded-lg border bg-card p-3 shadow-sm transition-all hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">{hit.conversationTitle}</span>
          <Badge variant="outline" className="shrink-0">
            {SEARCH_SCOPE_LABEL[hit.matchedIn]}
          </Badge>
        </span>
        <time dateTime={hit.createdAt} className="shrink-0 text-xs text-muted-foreground">
          {formatDateTime(hit.createdAt)}
        </time>
      </span>
      <span className="truncate text-sm text-muted-foreground">{hit.snippet}</span>
      <span className="text-xs text-muted-foreground">with {hit.employeeName}</span>
    </Link>
  );
}
