import type { MemoryScope, MemorySearchQuery } from "./types";

/**
 * Query keys for memory integration. Hierarchical so a mutation can invalidate
 * one parent's links (`memoryLinkKeys.links(scope, id)`) without disturbing the
 * picker's search cache.
 *
 * The picker's search carries the whole query in its key, so each distinct
 * search is its own cache entry — going back to a previous filter is instant.
 */
export const memoryLinkKeys = {
  all: ["memory-links"] as const,
  links: (scope: MemoryScope, parentId: string) =>
    ["memory-links", "list", scope, parentId] as const,
  searches: ["memory-links", "search"] as const,
  search: (query: MemorySearchQuery) => ["memory-links", "search", query] as const,
} as const;
