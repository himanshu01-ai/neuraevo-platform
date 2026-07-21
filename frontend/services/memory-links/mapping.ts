/**
 * Backend ⇄ frontend translation for memory integration.
 *
 * The one place the FastAPI `UserMemoryResponse` shape is spoken. Above the
 * adapter, callers see only `LinkedMemory`. The Memory Engine's field names and
 * casing (`memory_type`, `importance_score`) never leak into a component.
 */

import { z } from "zod";
import type { MemoryType } from "@/services/memory";
import type { LinkedMemory } from "./types";

const MEMORY_TYPE_VALUES = ["permanent", "working", "learned"] as const;

/** Mirrors `app.schemas.memory_link.UserMemoryResponse`. */
export const userMemorySchema = z.object({
  id: z.string(),
  employee_id: z.string(),
  employee_name: z.string(),
  memory_type: z.enum(MEMORY_TYPE_VALUES),
  content: z.string(),
  importance_score: z.number(),
  created_at: z.string(),
});

export type UserMemoryWire = z.infer<typeof userMemorySchema>;

/** Mirrors `app.schemas.memory_link.UserMemoryListResponse`. */
export const userMemoryListSchema = z.object({
  items: z.array(userMemorySchema),
  total: z.number(),
});

const TITLE_MAX = 80;

/** First non-empty line of the content, trimmed to a display length. */
function deriveTitle(content: string): string {
  const first = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean);
  if (!first) return "Untitled memory";
  return first.length > TITLE_MAX ? `${first.slice(0, TITLE_MAX - 1).trimEnd()}…` : first;
}

export function toLinkedMemory(raw: UserMemoryWire): LinkedMemory {
  return {
    id: raw.id,
    employeeId: raw.employee_id,
    employeeName: raw.employee_name,
    memoryType: raw.memory_type as MemoryType,
    content: raw.content,
    importanceScore: raw.importance_score,
    createdAt: raw.created_at,
    title: deriveTitle(raw.content),
  };
}
