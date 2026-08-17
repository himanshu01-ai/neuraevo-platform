"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { memoryKeys, memoryService, type SearchQuery } from "@/services/memory";
import { useMemoryStore } from "@/store/memory";
import { useSearchStore } from "@/store/memory";

/**
 * Server-state hooks for memory. Each wraps `services/memory`, so callers never
 * know whether the data came from a mock adapter or the Memory Engine.
 *
 * Memory is the least volatile data in this app — a stored fact doesn't change
 * because you looked at it — so the stale times are generous and nothing polls.
 * The frozen API is a plain REST resource with no live channel, so there would
 * be nothing to poll for.
 */
const LIST_STALE_TIME = 60_000;
const CATALOG_STALE_TIME = 600_000;

/**
 * The knowledge, narrowed by the current query.
 *
 * The query is part of the key, so each distinct search is its own cache entry
 * and going back to a previous filter is instant rather than a refetch. In
 * Sprint 17.9 this same key is what varies the request.
 */
export function useMemoryList(query: SearchQuery) {
  return useQuery({
    queryKey: memoryKeys.list(query),
    queryFn: () => memoryService.list(query),
    staleTime: LIST_STALE_TIME,
  });
}

export function useMemoryDetail(id: string | null) {
  return useQuery({
    queryKey: memoryKeys.detail(id ?? ""),
    queryFn: () => memoryService.detail(id as string),
    staleTime: LIST_STALE_TIME,
    // The workspace renders with nothing selected, so the panels ask for a
    // memory that may not exist yet. No id, no request.
    enabled: id !== null,
    retry: false,
  });
}

export function useCollections() {
  return useQuery({
    queryKey: memoryKeys.collections,
    queryFn: memoryService.collections,
    staleTime: LIST_STALE_TIME,
  });
}

/** One memory's history, or the whole workspace's when `memoryId` is null. */
export function useMemoryTimeline(memoryId: string | null) {
  return useQuery({
    queryKey: memoryKeys.timeline(memoryId),
    queryFn: () => memoryService.timeline(memoryId),
    staleTime: LIST_STALE_TIME,
  });
}

export function useKnowledgeGraph() {
  return useQuery({
    queryKey: memoryKeys.graph,
    queryFn: memoryService.graph,
    staleTime: LIST_STALE_TIME,
  });
}

export function useMemoryInsights() {
  return useQuery({
    queryKey: memoryKeys.insights,
    queryFn: memoryService.insights,
    staleTime: LIST_STALE_TIME,
  });
}

/** The owners the Owner facet offers. A roster changes rarely. */
export function useMemoryOwners() {
  return useQuery({
    queryKey: memoryKeys.owners,
    queryFn: memoryService.owners,
    staleTime: CATALOG_STALE_TIME,
  });
}

/** Every tag in use, for the Tags facet. */
export function useMemoryTags() {
  return useQuery({
    queryKey: memoryKeys.tags,
    queryFn: memoryService.tags,
    staleTime: CATALOG_STALE_TIME,
  });
}

/**
 * The query as the workspace actually asks it: the user's search, overlaid with
 * the one facet the browsing surface owns — the shelf you've clicked in the tree.
 *
 * Composed here rather than written into the search store so the tree and the
 * search panel stay independent: clicking a shelf shouldn't rewrite a query the
 * user built, and clearing the search shouldn't drop you out of the shelf.
 */
export function useWorkspaceQuery(): SearchQuery {
  const query = useSearchStore((s) => s.query);
  const selectedCollection = useMemoryStore((s) => s.selectedCollection);

  return useMemo(
    () => ({
      ...query,
      // The tree's shelf wins while one is picked; "every collection" defers to
      // whatever the search panel says.
      collection: selectedCollection ?? query.collection,
    }),
    [query, selectedCollection]
  );
}
