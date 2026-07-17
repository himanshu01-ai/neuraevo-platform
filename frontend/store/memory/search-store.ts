import { create } from "zustand";
import {
  EMPTY_SEARCH,
  clampImportance,
  type Collection,
  type Language,
  type MemoryKind,
  type MemoryStatus,
  type MemoryType,
  type SearchQuery,
} from "@/services/memory";

/**
 * The search query, as the user has built it up.
 *
 * Separate from `memory-store` because searching and browsing are different
 * jobs: the query is the *question* being asked of the knowledge, while the
 * memory store holds where you are in the *answer*. Keeping them apart is also
 * what lets the query be a single object — which is exactly the shape the
 * service takes, and the shape Sprint 17.9 will send down the wire.
 *
 * No results live here. The query is client state; what comes back is server
 * state and belongs to the Query cache (docs/09).
 */

interface SearchState {
  query: SearchQuery;

  setKeyword: (keyword: string) => void;
  toggleTag: (tag: string) => void;
  setCollection: (collection: Collection | "ALL") => void;
  setOwner: (ownerId: string | "ALL") => void;
  setLanguage: (language: Language | "ALL") => void;
  setKind: (kind: MemoryKind | "ALL") => void;
  setMemoryType: (memoryType: MemoryType | "ALL") => void;
  setStatus: (status: MemoryStatus | "ALL") => void;
  setFromDate: (day: string) => void;
  setToDate: (day: string) => void;
  setMinImportance: (score: number) => void;
  reset: () => void;
}

const patch = (next: Partial<SearchQuery>) => (s: SearchState) => ({ query: { ...s.query, ...next } });

export const useSearchStore = create<SearchState>()((set) => ({
  query: EMPTY_SEARCH,

  setKeyword: (keyword) => set(patch({ keyword })),

  toggleTag: (tag) =>
    set((s) => ({
      query: {
        ...s.query,
        tags: s.query.tags.includes(tag)
          ? s.query.tags.filter((t) => t !== tag)
          : [...s.query.tags, tag],
      },
    })),

  setCollection: (collection) => set(patch({ collection })),
  setOwner: (ownerId) => set(patch({ ownerId })),
  setLanguage: (language) => set(patch({ language })),
  setKind: (kind) => set(patch({ kind })),
  setMemoryType: (memoryType) => set(patch({ memoryType })),
  setStatus: (status) => set(patch({ status })),
  setFromDate: (fromDate) => set(patch({ fromDate })),
  setToDate: (toDate) => set(patch({ toDate })),
  setMinImportance: (score) => set(patch({ minImportance: clampImportance(score) })),
  reset: () => set({ query: EMPTY_SEARCH }),
}));

/** True when any facet is narrowing the knowledge — drives the "clear" affordance. */
export const hasActiveSearch = (query: SearchQuery): boolean =>
  query.keyword.trim() !== "" ||
  query.tags.length > 0 ||
  query.collection !== "ALL" ||
  query.ownerId !== "ALL" ||
  query.language !== "ALL" ||
  query.kind !== "ALL" ||
  query.memoryType !== "ALL" ||
  query.status !== "ALL" ||
  query.fromDate !== "" ||
  query.toDate !== "" ||
  query.minImportance > 0;

/** How many facets are active — for the "N filters" chip. */
export const activeFacetCount = (query: SearchQuery): number =>
  [
    query.keyword.trim() !== "",
    query.tags.length > 0,
    query.collection !== "ALL",
    query.ownerId !== "ALL",
    query.language !== "ALL",
    query.kind !== "ALL",
    query.memoryType !== "ALL",
    query.status !== "ALL",
    query.fromDate !== "" || query.toDate !== "",
    query.minImportance > 0,
  ].filter(Boolean).length;
