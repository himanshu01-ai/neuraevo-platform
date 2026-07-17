"use client";

import { Search, X } from "lucide-react";
import {
  COLLECTIONS,
  COLLECTION_LABEL,
  LANGUAGES,
  LANGUAGE_LABEL,
  MEMORY_KINDS,
  MEMORY_STATUSES,
  MEMORY_STATUS_LABEL,
  MEMORY_TYPES,
  MEMORY_TYPE_LABEL,
  type Collection,
  type Language,
  type MemoryKind,
  type MemoryStatus,
  type MemoryType,
} from "@/services/memory";
import { activeFacetCount, hasActiveSearch, useSearchStore } from "@/store/memory";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useMemoryOwners, useMemoryTags } from "../hooks/use-memory";
import { MEMORY_KIND_META } from "../models/memory-kinds";
import { cn } from "@/lib/utils";

export interface SearchPanelProps {
  /** Lays the facets out in a column (the search screen) or a row (the toolbar). */
  layout?: "stacked" | "inline";
  className?: string;
}

/**
 * Every way to narrow the knowledge.
 *
 * This is mock search: the adapter filters, it does not rank. There is no
 * relevance here to sort by, and inventing one would produce an ordering nothing
 * behind it could reproduce — so results come back in the order they're stored.
 *
 * Every control writes straight to the search store, and the list derives from
 * it, so the panel never holds a second copy of what's showing.
 */
export function SearchPanel({ layout = "stacked", className }: SearchPanelProps) {
  const query = useSearchStore((s) => s.query);
  const setKeyword = useSearchStore((s) => s.setKeyword);
  const toggleTag = useSearchStore((s) => s.toggleTag);
  const setCollection = useSearchStore((s) => s.setCollection);
  const setOwner = useSearchStore((s) => s.setOwner);
  const setLanguage = useSearchStore((s) => s.setLanguage);
  const setKind = useSearchStore((s) => s.setKind);
  const setMemoryType = useSearchStore((s) => s.setMemoryType);
  const setStatus = useSearchStore((s) => s.setStatus);
  const setFromDate = useSearchStore((s) => s.setFromDate);
  const setToDate = useSearchStore((s) => s.setToDate);
  const reset = useSearchStore((s) => s.reset);

  const owners = useMemoryOwners();
  const tags = useMemoryTags();

  const isFiltered = hasActiveSearch(query);
  const facets = activeFacetCount(query);
  const isInline = layout === "inline";

  return (
    <div className={cn("space-y-4", className)}>
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          type="search"
          value={query.keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="Search titles, summaries and content"
          aria-label="Search knowledge"
          className="pl-9"
        />
      </div>

      <div className={cn("gap-3", isInline ? "flex flex-wrap items-end" : "grid sm:grid-cols-2")}>
        <Field label="Collection" className={isInline ? "min-w-36" : undefined}>
          {({ id }) => (
            <Select
              id={id}
              value={query.collection}
              onChange={(event) => setCollection(event.target.value as Collection | "ALL")}
              className="h-9 text-xs"
            >
              <option value="ALL">Any collection</option>
              {COLLECTIONS.map((collection) => (
                <option key={collection} value={collection}>
                  {COLLECTION_LABEL[collection]}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Owner" className={isInline ? "min-w-36" : undefined}>
          {({ id }) => (
            <Select
              id={id}
              value={query.ownerId}
              onChange={(event) => setOwner(event.target.value)}
              className="h-9 text-xs"
            >
              <option value="ALL">Any owner</option>
              {(owners.data ?? []).map((owner) => (
                <option key={owner.employeeId} value={owner.employeeId}>
                  {owner.employeeName}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Type" className={isInline ? "min-w-36" : undefined}>
          {({ id }) => (
            <Select
              id={id}
              value={query.kind}
              onChange={(event) => setKind(event.target.value as MemoryKind | "ALL")}
              className="h-9 text-xs"
            >
              <option value="ALL">Any type</option>
              {MEMORY_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {MEMORY_KIND_META[kind].label}
                </option>
              ))}
            </Select>
          )}
        </Field>

        {/*
          Retention is the backend's own `memory_type`. It is a separate question
          from Type above — how long a memory lives, not what kind of thing it
          is — so it gets its own control rather than being folded in.
        */}
        <Field label="Retention" className={isInline ? "min-w-36" : undefined}>
          {({ id }) => (
            <Select
              id={id}
              value={query.memoryType}
              onChange={(event) => setMemoryType(event.target.value as MemoryType | "ALL")}
              className="h-9 text-xs"
            >
              <option value="ALL">Any retention</option>
              {MEMORY_TYPES.map((memoryType) => (
                <option key={memoryType} value={memoryType}>
                  {MEMORY_TYPE_LABEL[memoryType]}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Language" className={isInline ? "min-w-32" : undefined}>
          {({ id }) => (
            <Select
              id={id}
              value={query.language}
              onChange={(event) => setLanguage(event.target.value as Language | "ALL")}
              className="h-9 text-xs"
            >
              <option value="ALL">Any language</option>
              {LANGUAGES.map((language) => (
                <option key={language} value={language}>
                  {LANGUAGE_LABEL[language]}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Status" className={isInline ? "min-w-32" : undefined}>
          {({ id }) => (
            <Select
              id={id}
              value={query.status}
              onChange={(event) => setStatus(event.target.value as MemoryStatus | "ALL")}
              className="h-9 text-xs"
            >
              <option value="ALL">Any status</option>
              {MEMORY_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {MEMORY_STATUS_LABEL[status]}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Created from" className={isInline ? "min-w-36" : undefined}>
          {({ id }) => (
            <Input
              id={id}
              type="date"
              value={query.fromDate}
              onChange={(event) => setFromDate(event.target.value)}
              className="h-9 text-xs"
            />
          )}
        </Field>

        <Field label="Created to" className={isInline ? "min-w-36" : undefined}>
          {({ id }) => (
            <Input
              id={id}
              type="date"
              value={query.toDate}
              onChange={(event) => setToDate(event.target.value)}
              className="h-9 text-xs"
            />
          )}
        </Field>
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-foreground">Tags</legend>
        {/* Native checkboxes: a tag filter is a set of toggles, and the browser
            already knows how to make those keyboard-operable and announceable. */}
        <ul className="flex flex-wrap gap-1.5">
          {(tags.data ?? []).map((tag) => {
            const isOn = query.tags.includes(tag);
            return (
              <li key={tag}>
                <label
                  className={cn(
                    "inline-flex cursor-pointer items-center rounded-sm border px-2 py-1 text-xs transition-colors",
                    "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background",
                    isOn
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:border-primary/40"
                  )}
                >
                  <input
                    type="checkbox"
                    checked={isOn}
                    onChange={() => toggleTag(tag)}
                    className="sr-only"
                  />
                  #{tag}
                </label>
              </li>
            );
          })}
        </ul>
      </fieldset>

      {isFiltered ? (
        <div className="flex items-center gap-2 border-t pt-3">
          <Badge variant="primary">
            {facets} filter{facets === 1 ? "" : "s"}
          </Badge>
          <Button variant="ghost" size="sm" className="h-7" onClick={reset}>
            <X className="size-4" aria-hidden="true" />
            Clear all
          </Button>
        </div>
      ) : null}
    </div>
  );
}
