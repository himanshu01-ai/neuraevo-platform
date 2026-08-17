import { z } from "zod";
import { ApiError, request } from "../http";
import { toLinkedMemory, userMemoryListSchema, userMemorySchema } from "./mapping";
import {
  MemoryLinkError,
  type LinkedMemory,
  type MemoryLinksAdapter,
  type MemoryScope,
  type MemorySearchQuery,
} from "./types";

/**
 * Real memory-integration adapter, backed by the FastAPI endpoints added this
 * sprint. Implements the same `MemoryLinksAdapter` seam as the mock, so no
 * caller changes.
 *
 *   GET    /memories                                    the user's memories (+ search)
 *   GET    /tasks|workflows/{id}/memories               the ones it references
 *   POST   /tasks|workflows/{id}/memories               reference one
 *   DELETE /tasks|workflows/{id}/memories/{memoryId}    drop the reference
 *
 * Ownership and auth are the backend's; `services/http.ts` attaches and refreshes
 * the token. A memory's content is never copied — every write is a reference over
 * the record the Memory Engine owns.
 */

const listSchema = z.array(userMemorySchema);

function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new MemoryLinkError("unknown", "The server returned an unexpected response.");
  }
  return result.data;
}

/** Map a transport-level `ApiError` onto the memory-link domain's vocabulary. */
function toMemoryLinkError(error: unknown, fallback: string): MemoryLinkError {
  if (error instanceof MemoryLinkError) return error;

  if (error instanceof ApiError) {
    if (error.isNetworkError) return new MemoryLinkError("unavailable", error.message);
    // 404 covers a missing task/workflow, a memory that isn't the user's, and an
    // unlinked memory — all "not there for you", which is what the UI shows.
    if (error.status === 404) return new MemoryLinkError("not_found", error.message);
    if (error.status === 403) return new MemoryLinkError("forbidden", error.message);
    if (error.status >= 500) return new MemoryLinkError("unavailable", error.message);
    return new MemoryLinkError("unknown", error.message);
  }

  return new MemoryLinkError("unknown", fallback);
}

/** `task` → `tasks`, `workflow` → `workflows` — the resource segment. */
const resource = (scope: MemoryScope): string => (scope === "task" ? "tasks" : "workflows");

export class BackendMemoryLinksAdapter implements MemoryLinksAdapter {
  async list(scope: MemoryScope, parentId: string): Promise<LinkedMemory[]> {
    try {
      const raw = await request<unknown>(
        `/${resource(scope)}/${encodeURIComponent(parentId)}/memories`
      );
      return parseOrThrow(listSchema, raw).map(toLinkedMemory);
    } catch (error) {
      throw toMemoryLinkError(error, "Those memories couldn't be loaded.");
    }
  }

  async attach(
    scope: MemoryScope,
    parentId: string,
    memoryId: string
  ): Promise<LinkedMemory> {
    try {
      const raw = await request<unknown>(
        `/${resource(scope)}/${encodeURIComponent(parentId)}/memories`,
        { method: "POST", body: { memory_id: memoryId } }
      );
      return toLinkedMemory(parseOrThrow(userMemorySchema, raw));
    } catch (error) {
      throw toMemoryLinkError(error, "That memory couldn't be attached.");
    }
  }

  async detach(scope: MemoryScope, parentId: string, memoryId: string): Promise<void> {
    try {
      await request<void>(
        `/${resource(scope)}/${encodeURIComponent(parentId)}/memories/${encodeURIComponent(memoryId)}`,
        { method: "DELETE" }
      );
    } catch (error) {
      throw toMemoryLinkError(error, "That memory couldn't be removed.");
    }
  }

  async search(query: MemorySearchQuery): Promise<LinkedMemory[]> {
    const params = new URLSearchParams();
    if (query.keyword.trim()) params.set("q", query.keyword.trim());
    if (query.memoryType !== "ALL") params.set("memory_type", query.memoryType);
    if (query.minImportance > 0) params.set("min_importance", String(query.minImportance));
    params.set("limit", "100");
    const suffix = params.toString();

    try {
      const raw = await request<unknown>(`/memories${suffix ? `?${suffix}` : ""}`);
      return parseOrThrow(userMemoryListSchema, raw).items.map(toLinkedMemory);
    } catch (error) {
      throw toMemoryLinkError(error, "Your memories couldn't be loaded.");
    }
  }
}
