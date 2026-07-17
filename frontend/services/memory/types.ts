/**
 * Memory domain contracts — provider-independent. The memory feature depends
 * only on these types and the `MemoryAdapter` interface, never on a concrete
 * provider. Sprint 17.8 ships a deterministic mock adapter; a real backend
 * adapter can be dropped in later with zero changes to callers.
 *
 * ## What is real, and what this layer is projecting
 *
 * Unlike workflows, employees and tasks, the Memory Engine is **built and
 * frozen** (Sprint 2). Its contract is small and exact:
 *
 *     Memory = { id, employee_id, memory_type, content, importance_score, created_at }
 *     memory_type ∈ { permanent, working, learned }   (app/utils/constants.MemoryType)
 *     GET /memories?employee_id&memory_type&min_importance&limit&offset  (oldest first)
 *     GET /memories/stats → { total_memories, permanent_count, working_count,
 *                             learned_count, average_importance_score }
 *
 * Everything this workspace shows beyond those fields — titles, collections,
 * tags, language, size, status, links, summaries — has **no column behind it
 * today**. Rather than blur the two, every field below says which side it is on,
 * so Sprint 17.9 knows exactly what it can bind and what it must first decide.
 * CLAUDE.md says not to redesign Memory architecture, and this doesn't: it
 * carries the real contract intact and marks the rest as projection.
 *
 * Nothing here retrieves, embeds, ranks, or reasons. It describes what is
 * stored; the Memory Engine is what stores it.
 */

import type { CanvasPosition } from "@/services/workflows";
import type { StatusTone } from "@/types/domain";

// =====================================================================
// Backend-mirrored vocabulary
// =====================================================================

/**
 * **Backend contract.** Mirrors `app/utils/constants.MemoryType` exactly,
 * lowercase values and all: `permanent` are long-lived facts, `working` is
 * short-lived context for the current activity, `learned` is inferred from
 * interactions over time.
 *
 * It lives here rather than in `types/domain.ts` because that file mirrors
 * `backend/app/services/ai_employee/*`, and this enum is from `app/utils` — the
 * same reason `NODE_KINDS` and `TASK_STATES` sit in their own service layers.
 *
 * This is a *retention* classification, not a content one. It is not the
 * workspace's "Type" facet — see `MEMORY_KINDS`.
 */
export const MEMORY_TYPES = ["permanent", "working", "learned"] as const;
export type MemoryType = (typeof MEMORY_TYPES)[number];

export const MEMORY_TYPE_LABEL: Record<MemoryType, string> = {
  permanent: "Permanent",
  working: "Working",
  learned: "Learned",
};

/**
 * Retention → tone. Permanent is settled (success), working is in flight (info),
 * learned is inferred and therefore the least certain (neutral). Colour resolves
 * through the one `StatusTone` scale, as everywhere else.
 */
export const MEMORY_TYPE_TONE: Record<MemoryType, StatusTone> = {
  permanent: "success",
  working: "info",
  learned: "neutral",
};

/**
 * **Backend contract.** `importance_score` is a float the API constrains to
 * 0.0–1.0 inclusive. Kept as a ratio rather than a percentage so it round-trips
 * unchanged; format it for display, never store the formatted form.
 */
export const IMPORTANCE_MIN = 0;
export const IMPORTANCE_MAX = 1;

export const clampImportance = (score: number): number =>
  Math.min(IMPORTANCE_MAX, Math.max(IMPORTANCE_MIN, score));

// =====================================================================
// Projected vocabulary (no backend column yet)
// =====================================================================

/**
 * **Projection.** What kind of thing a memory is. This is the workspace's "Type"
 * facet and has no backend column — `Memory` stores free `content` and a
 * retention `memory_type`, nothing about form.
 *
 * Sprint 17.9 has to decide where this lives (a new column, or metadata). Until
 * then it is authored here and this is the only place it is declared.
 */
export const MEMORY_KINDS = [
  "document",
  "conversation",
  "knowledge",
  "procedure",
  "template",
  "artifact",
  "reference",
  "policy",
] as const;
export type MemoryKind = (typeof MEMORY_KINDS)[number];

/**
 * **Projection.** The shelves a memory can sit on. `custom` carries a free-text
 * name in `customCollection`, so a user isn't held to this list.
 */
export const COLLECTIONS = [
  "general",
  "projects",
  "research",
  "engineering",
  "marketing",
  "support",
  "personal",
  "custom",
] as const;
export type Collection = (typeof COLLECTIONS)[number];

export const COLLECTION_LABEL: Record<Collection, string> = {
  general: "General",
  projects: "Projects",
  research: "Research",
  engineering: "Engineering",
  marketing: "Marketing",
  support: "Support",
  personal: "Personal",
  custom: "Custom",
};

/** **Projection.** Where a memory stands in its own review cycle. */
export const MEMORY_STATUSES = ["active", "review", "archived"] as const;
export type MemoryStatus = (typeof MEMORY_STATUSES)[number];

export const MEMORY_STATUS_LABEL: Record<MemoryStatus, string> = {
  active: "Active",
  review: "Needs review",
  archived: "Archived",
};

export const MEMORY_STATUS_TONE: Record<MemoryStatus, StatusTone> = {
  active: "success",
  review: "warning",
  archived: "neutral",
};

/**
 * **Projection.** Languages a memory can be written in. BCP-47 primary subtags,
 * so a real `Content-Language` maps straight on.
 */
export const LANGUAGES = ["en", "de", "fr", "es", "hi"] as const;
export type Language = (typeof LANGUAGES)[number];

export const LANGUAGE_LABEL: Record<Language, string> = {
  en: "English",
  de: "German",
  fr: "French",
  es: "Spanish",
  hi: "Hindi",
};

// =====================================================================
// Links
// =====================================================================

/**
 * **Projection.** A memory the platform associates with an employee other than
 * its owner.
 *
 * The backend gives a memory exactly one `employee_id` (a required FK with
 * `cascade="all, delete-orphan"`), so "linked employees" is not a relation that
 * exists yet — `owner` below is the real one. Sprint 17.9 either adds a link
 * table or drops this facet; carrying it separately from `owner` keeps that
 * decision cheap.
 */
export interface EmployeeLink {
  employeeId: string;
  employeeName: string;
}

/** **Projection.** A workflow that reads this memory. No backend relation yet. */
export interface WorkflowLink {
  workflowId: string;
  workflowName: string;
}

// =====================================================================
// Memory
// =====================================================================

/** What the browser list, cards and tree need. */
export interface MemorySummary {
  /** **Backend.** `Memory.id`. */
  id: string;
  /** **Projection.** First line of `content` today; a real column in 17.9. */
  title: string;
  /** **Projection.** The workspace's Type facet. */
  kind: MemoryKind;
  /** **Backend.** `Memory.memory_type` — retention, not form. */
  memoryType: MemoryType;
  /** **Projection.** */
  collection: Collection;
  /** **Projection.** Set only when `collection` is `custom`. */
  customCollection: string;
  /** **Backend.** The one employee that owns this memory (`Memory.employee_id`). */
  owner: EmployeeLink;
  /** **Backend.** `Memory.created_at`, ISO 8601 in UTC. */
  createdAt: string;
  /** **Projection.** `Memory` has no `updated_at`; 17.9 must add one or drop this. */
  updatedAt: string;
  /** **Projection.** Byte size of the content. Formatted for display, never stored formatted. */
  sizeBytes: number;
  /** **Projection.** */
  language: Language;
  /** **Projection.** */
  tags: string[];
  /** **Projection.** */
  status: MemoryStatus;
  /** **Backend.** `Memory.importance_score`, 0–1. */
  importanceScore: number;
  /** **Projection.** One line on what this memory is for. */
  summary: string;
}

/** Everything a memory's own screens show. */
export interface MemoryDetail extends MemorySummary {
  /** **Backend.** `Memory.content` — the memory itself. */
  content: string;
  /** **Projection.** */
  linkedEmployees: EmployeeLink[];
  /** **Projection.** */
  linkedWorkflows: WorkflowLink[];
  /**
   * **Projection.** How often the platform has reached for this. The Memory
   * Engine counts nothing of the sort today.
   */
  usage: MemoryUsage;
}

/** **Projection.** Usage counters. Carried, never derived by the UI. */
export interface MemoryUsage {
  /** How many times a run has recalled this memory. */
  recallCount: number;
  /** The most recent recall, ISO 8601, or `null` when never recalled. */
  lastRecalledAt: string | null;
  /** Plain-language note on where it gets used. */
  note: string;
}

// =====================================================================
// Collections
// =====================================================================

export interface CollectionSummary {
  collection: Collection;
  /** The name to show — the label, or the custom name when `custom`. */
  name: string;
  description: string;
  /** How many memories sit here. Carried, never counted by the UI. */
  count: number;
  /** Total bytes across the collection. */
  sizeBytes: number;
}

// =====================================================================
// Knowledge graph
// =====================================================================

/**
 * **Projection.** What a node in the knowledge graph stands for.
 *
 * The Memory Engine stores no relations beyond `employee_id`, so this whole
 * graph is a picture of associations 17.9 must decide how to source. It is
 * modelled on the workflow/execution graphs so all three read the same way.
 */
export const GRAPH_NODE_KINDS = [
  "memory",
  "employee",
  "workflow",
  "task",
  "document",
  "collection",
] as const;
export type GraphNodeKind = (typeof GRAPH_NODE_KINDS)[number];

/** How two nodes are related. `RELATIONSHIP` is the unlabelled association. */
export const RELATIONSHIP_KINDS = [
  "OWNS",
  "LINKED",
  "DERIVED_FROM",
  "REFERENCES",
  "CONTAINS",
  "RELATIONSHIP",
] as const;
export type RelationshipKind = (typeof RELATIONSHIP_KINDS)[number];

export const RELATIONSHIP_LABEL: Record<RelationshipKind, string> = {
  OWNS: "owns",
  LINKED: "linked to",
  DERIVED_FROM: "derived from",
  REFERENCES: "references",
  CONTAINS: "contains",
  RELATIONSHIP: "related to",
};

export interface GraphNode {
  id: string;
  kind: GraphNodeKind;
  name: string;
  /** One line on what this node is. */
  detail: string;
  position: CanvasPosition;
  /** The memory this node stands for, when it stands for one. */
  memoryId: string | null;
}

/** A directed association: `sourceNode` → `targetNode`. */
export interface GraphEdge {
  id: string;
  sourceNode: string;
  targetNode: string;
  relationship: RelationshipKind;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// =====================================================================
// Timeline
// =====================================================================

export const TIMELINE_EVENT_KINDS = [
  "CREATED",
  "UPDATED",
  "LINKED",
  "IMPORTED",
  "REVIEWED",
  "ARCHIVED",
] as const;
export type TimelineEventKind = (typeof TIMELINE_EVENT_KINDS)[number];

export interface TimelineEvent {
  id: string;
  kind: TimelineEventKind;
  /** The memory this concerns, or `null` for a workspace-wide event. */
  memoryId: string | null;
  memoryTitle: string;
  /** One line naming what happened. Fixture copy — nothing is inferred. */
  summary: string;
  /** ISO 8601 in UTC. */
  at: string;
}

// =====================================================================
// Search
// =====================================================================

/**
 * Every facet the workspace can narrow by. `"ALL"` is the unset state.
 *
 * `keyword`, `memoryType` and `status` are the only ones the frozen API could
 * serve today (`memory_type`, plus a content scan); the rest need columns that
 * don't exist. Sprint 17.9 decides which move server-side — until then the mock
 * adapter answers all of them the same way, so callers don't change either way.
 */
export interface SearchQuery {
  keyword: string;
  tags: string[];
  collection: Collection | "ALL";
  ownerId: string | "ALL";
  language: Language | "ALL";
  kind: MemoryKind | "ALL";
  memoryType: MemoryType | "ALL";
  status: MemoryStatus | "ALL";
  /** ISO day (`"2026-07-01"`), inclusive. `""` is unset. */
  fromDate: string;
  toDate: string;
  /**
   * **Backend contract.** Only memories scoring at or above this. Mirrors the
   * API's `min_importance` query parameter, so 17.9 sends it rather than
   * filtering client-side. `0` is unset — every memory clears it.
   */
  minImportance: number;
}

export const EMPTY_SEARCH: SearchQuery = {
  keyword: "",
  tags: [],
  collection: "ALL",
  ownerId: "ALL",
  language: "ALL",
  kind: "ALL",
  memoryType: "ALL",
  status: "ALL",
  fromDate: "",
  toDate: "",
  minImportance: 0,
};

// =====================================================================
// Insights
// =====================================================================

/** One slice of a distribution. `ratio` is 0–1 of the whole. */
export interface DistributionSlice {
  label: string;
  count: number;
  ratio: number;
}

/** One step of the growth series. */
export interface GrowthPoint {
  /** ISO day. */
  day: string;
  /** Running total of memories at that day. */
  total: number;
}

/**
 * What the workspace reports about the knowledge as a whole.
 *
 * `totals` is the one part with a real endpoint behind it — it mirrors
 * `MemoryStatsResponse` field for field, so 17.9 binds it directly. Every other
 * section is aggregated by the mock from projected fields and would need the
 * backend to grow them first.
 */
export interface MemoryTotals {
  /** Mirrors `MemoryStatsResponse.total_memories`. */
  totalMemories: number;
  /** Mirrors `MemoryStatsResponse.permanent_count`. */
  permanentCount: number;
  /** Mirrors `MemoryStatsResponse.working_count`. */
  workingCount: number;
  /** Mirrors `MemoryStatsResponse.learned_count`. */
  learnedCount: number;
  /** Mirrors `MemoryStatsResponse.average_importance_score`, 0–1. */
  averageImportanceScore: number;
}

export interface MemoryInsights {
  totals: MemoryTotals;
  /** Memory Distribution — by retention. */
  distribution: DistributionSlice[];
  /** Knowledge Growth — running total over time. */
  growth: GrowthPoint[];
  /** Collection Usage. */
  collectionUsage: DistributionSlice[];
  /** Document Types — by kind. */
  kinds: DistributionSlice[];
  /** Language Distribution. */
  languages: DistributionSlice[];
  /** Top Linked Employees. */
  topEmployees: DistributionSlice[];
  /** Recent Changes. */
  recentChanges: TimelineEvent[];
  /** Total bytes across every memory. */
  totalSizeBytes: number;
}

// =====================================================================
// Import
// =====================================================================

/** What the import UI will accept. Descriptive — nothing is uploaded. */
export const SUPPORTED_IMPORT_TYPES = ["md", "txt", "pdf", "docx", "json", "csv"] as const;
export type ImportType = (typeof SUPPORTED_IMPORT_TYPES)[number];

export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;

export type ImportIssueLevel = "error" | "warning";

export interface ImportIssue {
  level: ImportIssueLevel;
  message: string;
}

/** One file staged for import, with whatever validation had to say about it. */
export interface ImportCandidate {
  id: string;
  name: string;
  sizeBytes: number;
  /** `null` when the extension isn't one we know. */
  type: ImportType | null;
  issues: ImportIssue[];
  /** The memory this would become. */
  preview: {
    title: string;
    kind: MemoryKind;
    collection: Collection;
    language: Language;
    excerpt: string;
  };
}

export interface ImportSummary {
  accepted: number;
  rejected: number;
  totalBytes: number;
  /** The memories that were created. Empty in the mock — nothing is uploaded. */
  createdIds: string[];
  note: string;
}

// =====================================================================
// Errors & the adapter seam
// =====================================================================

export type MemoryErrorCode = "not_found" | "unavailable" | "invalid_import" | "unknown";

export class MemoryError extends Error {
  code: MemoryErrorCode;
  constructor(code: MemoryErrorCode, message: string) {
    super(message);
    this.name = "MemoryError";
    this.code = code;
  }
}

/**
 * The single seam every memory backend must implement.
 *
 * `list` takes the whole `SearchQuery` rather than a handful of arguments: the
 * frozen API already filters server-side (`memory_type`, `min_importance`,
 * `limit`/`offset`), so 17.9 will want to push facets down the wire, and a
 * single query object lets it do that without touching a caller.
 */
export interface MemoryAdapter {
  list(query: SearchQuery): Promise<MemorySummary[]>;
  detail(id: string): Promise<MemoryDetail>;
  collections(): Promise<CollectionSummary[]>;
  timeline(memoryId: string | null): Promise<TimelineEvent[]>;
  graph(): Promise<KnowledgeGraph>;
  insights(): Promise<MemoryInsights>;
  /** Every owner that appears in the roster, for the Owner facet. */
  owners(): Promise<EmployeeLink[]>;
  /** Every tag in use, for the Tags facet. */
  tags(): Promise<string[]>;
  /** Validates staged files. Never uploads: returns what *would* happen. */
  validateImport(files: { name: string; sizeBytes: number }[]): Promise<ImportCandidate[]>;
  /** Reports what an import would produce. Creates nothing. */
  summariseImport(candidates: ImportCandidate[]): Promise<ImportSummary>;
}
