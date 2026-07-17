import { MockMemoryAdapter } from "./mock-adapter";
import type { ImportCandidate, MemoryAdapter, SearchQuery } from "./types";

/**
 * The app's single entry point to memory data. Swapping providers = swapping
 * this one adapter; callers (the feature hooks) never change. No fetch/axios/SDKs,
 * no vector client, no embedding model.
 */
const adapter: MemoryAdapter = new MockMemoryAdapter();

export const memoryService = {
  list: (query: SearchQuery) => adapter.list(query),
  detail: (id: string) => adapter.detail(id),
  collections: () => adapter.collections(),
  timeline: (memoryId: string | null) => adapter.timeline(memoryId),
  graph: () => adapter.graph(),
  insights: () => adapter.insights(),
  owners: () => adapter.owners(),
  tags: () => adapter.tags(),
  validateImport: (files: { name: string; sizeBytes: number }[]) => adapter.validateImport(files),
  summariseImport: (candidates: ImportCandidate[]) => adapter.summariseImport(candidates),
};

export type MemoryService = typeof memoryService;
