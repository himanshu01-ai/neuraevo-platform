import { ApiError, request } from "../http";
import {
  applyFacets,
  deriveCollections,
  deriveGraph,
  deriveInsights,
  deriveOwners,
  deriveTimeline,
  summariseImport,
  toMemoryDetail,
  toSummary,
  userMemoryListSchema,
  validateImportFiles,
} from "./mapping";
import {
  MemoryError,
  type CollectionSummary,
  type EmployeeLink,
  type ImportCandidate,
  type ImportSummary,
  type KnowledgeGraph,
  type MemoryAdapter,
  type MemoryDetail,
  type MemoryInsights,
  type MemorySummary,
  type SearchQuery,
  type TimelineEvent,
} from "./types";

/**
 * Real Memory workspace adapter, backed by the Sprint 2 Memory Engine through
 * the user-wide `GET /memories` endpoint (the same one the memory-link surface
 * already trusts). It implements the same `MemoryAdapter` seam as the mock, so
 * no caller — page, hook, or component — changes.
 *
 *   GET /memories?q=&memory_type=&min_importance=&limit=&offset=
 *       the authenticated user's memories across every employee (+ search)
 *
 * The Memory Engine stores a flat record, so the workspace's richer surfaces
 * (collections, insights, timeline, graph, owners) are *derived here from the
 * real records* rather than fetched from columns that do not exist — one source
 * of truth, internally consistent, and honestly neutral where the engine has no
 * data (see `mapping.ts`). This replaces the Sprint 17 fixtures: the workspace
 * now shows the user's real memories, not invented ones. Tags have no backend,
 * so that facet is honestly empty; import validation is pure and client-side —
 * nothing is uploaded here.
 */

/** The most memories a single request pulls for the aggregate surfaces. */
const AGGREGATE_LIMIT = 100;

/** Map a transport-level `ApiError` onto the memory domain's vocabulary. */
function toMemoryError(error: unknown, fallback: string): MemoryError {
  if (error instanceof MemoryError) return error;
  if (error instanceof ApiError) {
    if (error.isNetworkError || error.status >= 500) {
      return new MemoryError("unavailable", "The memory service is unavailable right now.");
    }
    return new MemoryError("unknown", error.message);
  }
  return new MemoryError("unknown", fallback);
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export class BackendMemoryAdapter implements MemoryAdapter {
  /**
   * Fetch the user's memories as workspace records. `search` pushes the three
   * facets the engine serves (`q`, `memory_type`, `min_importance`) to the
   * server; the aggregate surfaces call it unfiltered to derive from the whole.
   */
  private async fetchDetails(search?: SearchQuery): Promise<MemoryDetail[]> {
    const path =
      "/memories" +
      buildQuery({
        q: search?.keyword.trim() || undefined,
        memory_type:
          search && search.memoryType !== "ALL" ? search.memoryType : undefined,
        min_importance:
          search && search.minImportance > 0 ? search.minImportance : undefined,
        limit: AGGREGATE_LIMIT,
      });
    try {
      const raw = await request<unknown>(path);
      const parsed = userMemoryListSchema.safeParse(raw);
      if (!parsed.success) {
        throw new MemoryError("unknown", "The server returned an unexpected response.");
      }
      return parsed.data.items.map(toMemoryDetail);
    } catch (error) {
      throw toMemoryError(error, "Your memories couldn't be loaded.");
    }
  }

  async list(query: SearchQuery): Promise<MemorySummary[]> {
    const rows = await this.fetchDetails(query);
    // The engine served keyword/type/importance; the remaining facets narrow
    // the mapped records here so the whole facet UI keeps working.
    return applyFacets(rows.map(toSummary), query);
  }

  async detail(id: string): Promise<MemoryDetail> {
    // No user-scoped single-memory endpoint exists; the list is the one door
    // to a user-wide memory, so detail is resolved from it.
    const rows = await this.fetchDetails();
    const found = rows.find((m) => m.id === id);
    if (!found) throw new MemoryError("not_found", "That memory doesn't exist.");
    return found;
  }

  async collections(): Promise<CollectionSummary[]> {
    return deriveCollections(await this.fetchDetails());
  }

  async timeline(memoryId: string | null): Promise<TimelineEvent[]> {
    return deriveTimeline(await this.fetchDetails(), memoryId);
  }

  async graph(): Promise<KnowledgeGraph> {
    return deriveGraph(await this.fetchDetails());
  }

  async insights(): Promise<MemoryInsights> {
    return deriveInsights(await this.fetchDetails());
  }

  async owners(): Promise<EmployeeLink[]> {
    return deriveOwners(await this.fetchDetails());
  }

  async tags(): Promise<string[]> {
    // The Memory Engine has no tag column, so the facet is honestly empty
    // rather than invented.
    return [];
  }

  async validateImport(
    files: { name: string; sizeBytes: number }[]
  ): Promise<ImportCandidate[]> {
    const existing = await this.fetchDetails();
    return validateImportFiles(files, existing.map((m) => m.title));
  }

  async summariseImport(candidates: ImportCandidate[]): Promise<ImportSummary> {
    return summariseImport(candidates);
  }
}
