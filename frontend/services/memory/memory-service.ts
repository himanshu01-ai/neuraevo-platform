import { env } from "@/lib/env";
import { BackendMemoryAdapter } from "./backend-adapter";
import { MockMemoryAdapter } from "./mock-adapter";
import type { ImportCandidate, MemoryAdapter, SearchQuery } from "./types";

/**
 * The app's single entry point to memory data, and the only place that knows
 * which adapter is active. Callers (the feature hooks) never import an adapter.
 *
 * Sprint 23 wired the memory workspace to the real Sprint 2 Memory Engine:
 * `backend` (default) shows the user's real memories through `GET /memories`,
 * with the workspace's richer surfaces derived from those real records; `mock`
 * keeps the Sprint 17 offline fixtures for UI-only work, selectable via
 * `NEXT_PUBLIC_MEMORY_WORKSPACE_ADAPTER=mock`.
 */
const adapter: MemoryAdapter =
  env.NEXT_PUBLIC_MEMORY_WORKSPACE_ADAPTER === "mock"
    ? new MockMemoryAdapter()
    : new BackendMemoryAdapter();

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
