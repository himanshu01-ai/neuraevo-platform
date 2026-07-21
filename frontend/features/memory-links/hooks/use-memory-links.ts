"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  memoryLinkKeys,
  memoryLinksService,
  type MemoryScope,
  type MemorySearchQuery,
} from "@/services/memory-links";

/**
 * Server-state hooks for memory integration. Each wraps `services/memory-links`,
 * so callers never know whether the data came from a mock adapter or the
 * FastAPI backend.
 *
 * Linked memories change only when the user attaches or detaches one, and the
 * picker's roster changes rarely, so the stale times are generous and nothing
 * polls — a memory reference is not live data.
 */
const LINKS_STALE_TIME = 30_000;
const SEARCH_STALE_TIME = 60_000;

export function useLinkedMemories(scope: MemoryScope, parentId: string) {
  return useQuery({
    queryKey: memoryLinkKeys.links(scope, parentId),
    queryFn: () => memoryLinksService.list(scope, parentId),
    staleTime: LINKS_STALE_TIME,
  });
}

/** The attach picker's source. `enabled` keeps it idle until the picker opens. */
export function useMemorySearch(query: MemorySearchQuery, enabled: boolean) {
  return useQuery({
    queryKey: memoryLinkKeys.search(query),
    queryFn: () => memoryLinksService.search(query),
    staleTime: SEARCH_STALE_TIME,
    enabled,
  });
}

export function useAttachMemory(scope: MemoryScope, parentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (memoryId: string) =>
      memoryLinksService.attach(scope, parentId, memoryId),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: memoryLinkKeys.links(scope, parentId) }),
  });
}

export function useDetachMemory(scope: MemoryScope, parentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (memoryId: string) =>
      memoryLinksService.detach(scope, parentId, memoryId),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: memoryLinkKeys.links(scope, parentId) }),
  });
}
