import type { SearchQuery } from "./types";

/**
 * Query keys for the memory resource. Hierarchical so a mutation can invalidate
 * one memory (`memoryKeys.detail(id)`) or every list (`memoryKeys.lists`).
 *
 * `list` carries the whole query in its key, which is what makes each distinct
 * search its own cache entry — going back to a previous filter is then instant
 * rather than a refetch. The frozen API filters server-side, so in Sprint 17.9
 * this key is also exactly what varies the request.
 *
 * Scoped to this resource for now; the shapes follow the convention of the
 * central `services/query-keys.ts` factory described in docs/09, so this table
 * lifts into it unchanged when that gets built.
 */
export const memoryKeys = {
  all: ["memory"] as const,
  lists: ["memory", "list"] as const,
  list: (query: SearchQuery) => ["memory", "list", query] as const,
  detail: (id: string) => ["memory", "detail", id] as const,
  collections: ["memory", "collections"] as const,
  timeline: (memoryId: string | null) => ["memory", "timeline", memoryId] as const,
  graph: ["memory", "graph"] as const,
  insights: ["memory", "insights"] as const,
  owners: ["memory", "owners"] as const,
  tags: ["memory", "tags"] as const,
} as const;
