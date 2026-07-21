/**
 * Memory-integration contracts — provider-independent.
 *
 * This is the seam for the real backend integration added this sprint: linking
 * existing Memory Engine records to tasks and workflows, and reading a user's
 * memories across all their employees (the attach picker's source). The
 * standalone memory *workspace* (`services/memory`) is a separate, heavily
 * projected visualisation and keeps its own adapter — this module carries only
 * the parts the backend genuinely serves.
 *
 * A `LinkedMemory` is exactly the backend's `UserMemoryResponse`: the real
 * Memory columns plus the owning employee's name (memories referenced by a task
 * or workflow can belong to different employees, so each carries its owner).
 * Nothing here is projected — every field has a column behind it.
 */

import type { MemoryType } from "@/services/memory";

/** The two things a memory can be referenced from. */
export type MemoryScope = "task" | "workflow";

/** A memory as it appears in a task/workflow reference list or the picker. */
export interface LinkedMemory {
  /** **Backend.** `Memory.id`. */
  id: string;
  /** **Backend.** The employee that owns the memory (`Memory.employee_id`). */
  employeeId: string;
  /** **Backend.** That employee's name, joined server-side. */
  employeeName: string;
  /** **Backend.** `Memory.memory_type` — retention (permanent/working/learned). */
  memoryType: MemoryType;
  /** **Backend.** `Memory.content` — the memory itself. */
  content: string;
  /** **Backend.** `Memory.importance_score`, 0–1. */
  importanceScore: number;
  /** **Backend.** `Memory.created_at`, ISO 8601 in UTC. */
  createdAt: string;
  /** First non-empty line of `content`, trimmed — a display title. */
  title: string;
}

/**
 * The picker's query. `keyword` searches memory content server-side (the API's
 * `q`), `memoryType`/`minImportance` reuse the Memory Engine's own filters.
 */
export interface MemorySearchQuery {
  keyword: string;
  memoryType: MemoryType | "ALL";
  /** Only memories scoring at or above this. `0` is unset. */
  minImportance: number;
}

export const EMPTY_MEMORY_SEARCH: MemorySearchQuery = {
  keyword: "",
  memoryType: "ALL",
  minImportance: 0,
};

// --- Errors & the adapter seam ------------------------------------------

export type MemoryLinkErrorCode =
  | "not_found"
  | "forbidden"
  | "unavailable"
  | "unknown";

export class MemoryLinkError extends Error {
  code: MemoryLinkErrorCode;
  constructor(code: MemoryLinkErrorCode, message: string) {
    super(message);
    this.name = "MemoryLinkError";
    this.code = code;
  }
}

/** The single seam every memory-integration backend must implement. */
export interface MemoryLinksAdapter {
  /** The memories a task or workflow references, in link order. */
  list(scope: MemoryScope, parentId: string): Promise<LinkedMemory[]>;
  /** Reference an existing memory. Idempotent — a repeat returns it unchanged. */
  attach(scope: MemoryScope, parentId: string, memoryId: string): Promise<LinkedMemory>;
  /** Drop a reference. The memory itself is never deleted. */
  detach(scope: MemoryScope, parentId: string, memoryId: string): Promise<void>;
  /** The user's memories across every employee, for the attach picker. */
  search(query: MemorySearchQuery): Promise<LinkedMemory[]>;
}
