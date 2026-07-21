import { env } from "@/lib/env";
import { BackendMemoryLinksAdapter } from "./backend-adapter";
import { MockMemoryLinksAdapter } from "./mock-adapter";
import type { MemoryLinksAdapter, MemoryScope, MemorySearchQuery } from "./types";

/**
 * The app's single entry point to memory integration, and the only place that
 * knows which adapter is active. Callers (the feature hooks) never import an
 * adapter.
 *
 * `backend` (default) talks to the FastAPI memory-link endpoints; `mock` keeps
 * an offline adapter for UI-only work. The choice is app-wide, so mock and real
 * memory links are never mixed in one view.
 */
const adapter: MemoryLinksAdapter =
  env.NEXT_PUBLIC_MEMORY_ADAPTER === "mock"
    ? new MockMemoryLinksAdapter()
    : new BackendMemoryLinksAdapter();

export const memoryLinksService = {
  list: (scope: MemoryScope, parentId: string) => adapter.list(scope, parentId),
  attach: (scope: MemoryScope, parentId: string, memoryId: string) =>
    adapter.attach(scope, parentId, memoryId),
  detach: (scope: MemoryScope, parentId: string, memoryId: string) =>
    adapter.detach(scope, parentId, memoryId),
  search: (query: MemorySearchQuery) => adapter.search(query),
};

export type MemoryLinksService = typeof memoryLinksService;
