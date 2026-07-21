"use client";

import { useEffect, useMemo, useState } from "react";
import { Brain, Check, Plus, Search, X } from "lucide-react";
import { MEMORY_TYPE_LABEL, MEMORY_TYPE_TONE, type MemoryType } from "@/services/memory";
import { EMPTY_MEMORY_SEARCH, type MemoryScope } from "@/services/memory-links";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";
import {
  useAttachMemory,
  useDetachMemory,
  useLinkedMemories,
  useMemorySearch,
} from "../hooks/use-memory-links";

/**
 * The memories a task or workflow references, with attach and detach (Sprint 20).
 *
 * A reference is over an existing Memory Engine record — the same memory an
 * employee owns — never a copy. Attaching picks from the user's own memories
 * (across every employee); detaching drops only the reference. Content-only, to
 * sit inside a `<Panel>` the way the run-history and artifact lists do.
 *
 * The type badge is composed here from the shared `Badge` and the memory
 * vocabulary in `services/memory` rather than imported from the memory feature —
 * features read services and shared primitives, not each other.
 */
export interface LinkedMemoriesProps {
  scope: MemoryScope;
  parentId: string;
}

const NOUN: Record<MemoryScope, string> = { task: "task", workflow: "workflow" };

function MemoryTypeBadge({ memoryType }: { memoryType: MemoryType }) {
  const tone = MEMORY_TYPE_TONE[memoryType];
  return (
    <Badge variant={TONE_VARIANT[tone]} className="shrink-0">
      <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone])} />
      {MEMORY_TYPE_LABEL[memoryType]}
    </Badge>
  );
}

/** Debounce a fast-changing value so the picker doesn't query every keystroke. */
function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(handle);
  }, [value, delayMs]);
  return debounced;
}

export function LinkedMemories({ scope, parentId }: LinkedMemoriesProps) {
  const noun = NOUN[scope];
  const linksQuery = useLinkedMemories(scope, parentId);
  const attach = useAttachMemory(scope, parentId);
  const detach = useDetachMemory(scope, parentId);

  const [picking, setPicking] = useState(false);
  const [keyword, setKeyword] = useState("");
  const debouncedKeyword = useDebounced(keyword, 250);
  const [notice, setNotice] = useState<{ tone: "error"; message: string } | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const searchQuery = useMemo(
    () => ({ ...EMPTY_MEMORY_SEARCH, keyword: debouncedKeyword }),
    [debouncedKeyword]
  );
  const search = useMemorySearch(searchQuery, picking);

  const linked = linksQuery.data ?? [];
  const linkedIds = useMemo(() => new Set(linked.map((m) => m.id)), [linked]);
  const candidates = (search.data ?? []).filter((m) => !linkedIds.has(m.id));

  const handleAttach = (memoryId: string) => {
    setNotice(null);
    setPendingId(memoryId);
    attach.mutate(memoryId, {
      onError: (error) =>
        setNotice({
          tone: "error",
          message: error instanceof Error ? error.message : "That memory couldn't be attached.",
        }),
      onSettled: () => setPendingId(null),
    });
  };

  const handleDetach = (memoryId: string) => {
    setNotice(null);
    setPendingId(memoryId);
    detach.mutate(memoryId, {
      onError: (error) =>
        setNotice({
          tone: "error",
          message: error instanceof Error ? error.message : "That memory couldn't be removed.",
        }),
      onSettled: () => setPendingId(null),
    });
  };

  return (
    <div className="space-y-3">
      {notice ? <Alert variant="error">{notice.message}</Alert> : null}

      {linksQuery.isPending ? (
        <LoadingState rows={2} />
      ) : linksQuery.isError ? (
        <p className="text-sm text-muted-foreground">
          These memories couldn&apos;t be loaded. Try again in a moment.
        </p>
      ) : linked.length === 0 ? (
        <EmptyState
          compact
          icon={Brain}
          title="No memories linked"
          description={`Attach a memory to give this ${noun} reference material.`}
        />
      ) : (
        <ol className="-mx-2 space-y-0.5">
          {linked.map((memory) => (
            <li key={memory.id} className="flex items-start gap-3 rounded-md px-2 py-2">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-foreground" title={memory.content}>
                  {memory.title}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  <MemoryTypeBadge memoryType={memory.memoryType} />
                  <span className="inline-flex items-center gap-1">
                    <Avatar name={memory.employeeName} className="size-4 text-[0.5rem]" />
                    {memory.employeeName}
                  </span>
                  <span className="tabular-nums">
                    {Math.round(memory.importanceScore * 100)}% importance
                  </span>
                </span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 text-muted-foreground hover:text-destructive"
                disabled={pendingId === memory.id}
                onClick={() => handleDetach(memory.id)}
                aria-label={`Remove ${memory.title}`}
              >
                <X className="size-3.5" aria-hidden="true" />
                Remove
              </Button>
            </li>
          ))}
        </ol>
      )}

      {picking ? (
        <div className="rounded-md border bg-background p-3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="Search your memories…"
              aria-label="Search memories to attach"
              className="pl-9"
              autoFocus
            />
          </div>

          <div className="mt-3 max-h-64 overflow-y-auto">
            {search.isPending ? (
              <LoadingState rows={2} />
            ) : search.isError ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                Your memories couldn&apos;t be loaded.
              </p>
            ) : candidates.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                {keyword.trim()
                  ? "No memories match that search."
                  : "Every memory is already linked, or you have none yet."}
              </p>
            ) : (
              <ol className="-mx-1 space-y-0.5">
                {candidates.map((memory) => (
                  <li key={memory.id} className="flex items-start gap-3 rounded-md px-1 py-1.5">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-foreground" title={memory.content}>
                        {memory.title}
                      </span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        <MemoryTypeBadge memoryType={memory.memoryType} />
                        <span>{memory.employeeName}</span>
                      </span>
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0"
                      disabled={pendingId === memory.id}
                      onClick={() => handleAttach(memory.id)}
                    >
                      <Check className="size-3.5" aria-hidden="true" />
                      Attach
                    </Button>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="mt-3 flex justify-end">
            <Button variant="ghost" size="sm" onClick={() => setPicking(false)}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => {
            setNotice(null);
            setPicking(true);
          }}
        >
          <Plus className="size-3.5" aria-hidden="true" />
          Attach memory
        </Button>
      )}
    </div>
  );
}
