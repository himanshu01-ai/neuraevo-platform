import { z } from "zod";
import { COLUMN_PITCH, ROW_PITCH } from "./knowledge-graph";
import {
  COLLECTION_LABEL,
  LANGUAGE_LABEL,
  MAX_IMPORT_BYTES,
  MEMORY_TYPES,
  MEMORY_TYPE_LABEL,
  SUPPORTED_IMPORT_TYPES,
  clampImportance,
  type Collection,
  type CollectionSummary,
  type DistributionSlice,
  type EmployeeLink,
  type GraphEdge,
  type GraphNode,
  type GrowthPoint,
  type ImportCandidate,
  type ImportIssue,
  type ImportSummary,
  type ImportType,
  type KnowledgeGraph,
  type Language,
  type MemoryDetail,
  type MemoryInsights,
  type MemoryKind,
  type MemorySummary,
  type MemoryTotals,
  type MemoryType,
  type SearchQuery,
  type TimelineEvent,
} from "./types";

/**
 * Real ↔ workspace mapping for the Memory workspace (Sprint 23).
 *
 * The Memory Engine stores a flat record — id, owning employee, retention type,
 * content, importance, created-at — and nothing of the workspace's *projected*
 * facets (form, collection, language, tags, review status, usage). So this
 * module maps the real columns faithfully and fills the projections with honest,
 * uniform neutrals rather than inventing variety: a real memory shown as it
 * actually is, not a fabricated one. Every read surface the workspace offers
 * (list, detail, collections, insights, timeline, graph, owners) is then derived
 * from these real records here, so the whole workspace is internally consistent
 * with one source of truth — the user's real memories.
 */

// --- Wire shape ----------------------------------------------------------

/** One row of `GET /memories` (the user-wide `UserMemoryResponse`). */
export const userMemorySchema = z.object({
  id: z.string(),
  employee_id: z.string(),
  employee_name: z.string(),
  memory_type: z.string(),
  content: z.string(),
  importance_score: z.number(),
  created_at: z.string(),
});

export const userMemoryListSchema = z.object({
  items: z.array(userMemorySchema),
  total: z.number(),
});

export type UserMemoryRow = z.infer<typeof userMemorySchema>;

// --- Neutral projections -------------------------------------------------
//
// The engine has no column behind these, so a single honest default beats
// invented diversity. They are named constants so the intent reads plainly.

const DEFAULT_KIND: MemoryKind = "knowledge";
const DEFAULT_COLLECTION: Collection = "general";
const DEFAULT_LANGUAGE: Language = "en";

const KNOWN_MEMORY_TYPES = new Set<string>(MEMORY_TYPES);

/** The retention type, defaulting anything unexpected to `learned`. */
function toMemoryType(raw: string): MemoryType {
  return KNOWN_MEMORY_TYPES.has(raw) ? (raw as MemoryType) : "learned";
}

/** UTF-8 byte length of the content — the real size, computed not stored. */
function byteLength(content: string): number {
  return new TextEncoder().encode(content).length;
}

/** The first non-empty line of the content, trimmed for a heading. */
function firstLine(content: string): string {
  const line = content
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.length > 0);
  const heading = (line ?? "Untitled memory").replace(/\s+/g, " ");
  return heading.length > 80 ? `${heading.slice(0, 79).trimEnd()}…` : heading;
}

/** Map one real memory row to the workspace's detail shape. */
export function toMemoryDetail(row: UserMemoryRow): MemoryDetail {
  const owner: EmployeeLink = {
    employeeId: row.employee_id,
    employeeName: row.employee_name,
  };
  const title = firstLine(row.content);
  return {
    id: row.id,
    title,
    kind: DEFAULT_KIND,
    memoryType: toMemoryType(row.memory_type),
    collection: DEFAULT_COLLECTION,
    customCollection: "",
    owner,
    createdAt: row.created_at,
    updatedAt: row.created_at,
    sizeBytes: byteLength(row.content),
    language: DEFAULT_LANGUAGE,
    tags: [],
    status: "active",
    importanceScore: clampImportance(row.importance_score),
    summary: title,
    content: row.content,
    linkedEmployees: [owner],
    linkedWorkflows: [],
    usage: {
      recallCount: 0,
      lastRecalledAt: null,
      note: "Recall tracking isn't reported by the Memory Engine yet.",
    },
  };
}

export const toSummary = (memory: MemoryDetail): MemorySummary => {
  const { content: _c, linkedEmployees: _le, linkedWorkflows: _lw, usage: _u, ...summary } = memory;
  return summary;
};

// --- Client-side facets (over already-fetched real records) --------------
//
// `keyword`, `memoryType` and `minImportance` are pushed to the server; the
// rest narrow the mapped records here so the workspace's facet UI keeps working.

const isoDay = (iso: string): string => iso.slice(0, 10);

export function applyFacets(rows: MemorySummary[], query: SearchQuery): MemorySummary[] {
  const from = query.fromDate || null;
  const to = query.toDate || null;
  return rows.filter((m) => {
    if (query.ownerId !== "ALL" && m.owner.employeeId !== query.ownerId) return false;
    if (query.collection !== "ALL" && m.collection !== query.collection) return false;
    if (query.language !== "ALL" && m.language !== query.language) return false;
    if (query.kind !== "ALL" && m.kind !== query.kind) return false;
    if (query.status !== "ALL" && m.status !== query.status) return false;
    if (query.tags.length > 0 && !query.tags.every((tag) => m.tags.includes(tag))) return false;
    const day = isoDay(m.createdAt);
    if (from && day < from) return false;
    if (to && day > to) return false;
    return true;
  });
}

// --- Derived aggregate surfaces (all from the real records) --------------

const slice = (label: string, count: number, total: number): DistributionSlice => ({
  label,
  count,
  ratio: total === 0 ? 0 : count / total,
});

export function deriveOwners(rows: MemoryDetail[]): EmployeeLink[] {
  const byId = new Map<string, EmployeeLink>();
  for (const m of rows) byId.set(m.owner.employeeId, m.owner);
  return [...byId.values()].sort((a, b) => a.employeeName.localeCompare(b.employeeName));
}

export function deriveCollections(rows: MemoryDetail[]): CollectionSummary[] {
  const here = rows.filter((m) => m.collection === DEFAULT_COLLECTION);
  return [
    {
      collection: DEFAULT_COLLECTION,
      name: COLLECTION_LABEL[DEFAULT_COLLECTION],
      description: "Every memory the platform holds for you.",
      count: here.length,
      sizeBytes: here.reduce((sum, m) => sum + m.sizeBytes, 0),
    },
  ];
}

export function deriveTimeline(
  rows: MemoryDetail[],
  memoryId: string | null
): TimelineEvent[] {
  return rows
    .filter((m) => memoryId === null || m.id === memoryId)
    .map((m) => ({
      id: `tl_${m.id}`,
      kind: "CREATED" as const,
      memoryId: m.id,
      memoryTitle: m.title,
      summary: `${m.owner.employeeName} recorded this ${MEMORY_TYPE_LABEL[m.memoryType].toLowerCase()} memory`,
      at: m.createdAt,
    }))
    .sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
}

export function deriveGraph(rows: MemoryDetail[]): KnowledgeGraph {
  const owners = deriveOwners(rows);
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  owners.forEach((owner, row) => {
    nodes.push({
      id: `emp_${owner.employeeId}`,
      kind: "employee",
      name: owner.employeeName,
      detail: "AI employee",
      position: { x: 0, y: row * ROW_PITCH },
      memoryId: null,
    });
  });

  rows.forEach((m, index) => {
    nodes.push({
      id: `mem_${m.id}`,
      kind: "memory",
      name: m.title,
      detail: MEMORY_TYPE_LABEL[m.memoryType],
      position: { x: COLUMN_PITCH, y: index * ROW_PITCH },
      memoryId: m.id,
    });
    edges.push({
      id: `owns_${m.owner.employeeId}_${m.id}`,
      sourceNode: `emp_${m.owner.employeeId}`,
      targetNode: `mem_${m.id}`,
      relationship: "OWNS",
    });
  });

  return { nodes, edges };
}

function growthSeries(rows: MemoryDetail[]): GrowthPoint[] {
  const byDay = new Map<string, number>();
  for (const m of rows) {
    const day = isoDay(m.createdAt);
    byDay.set(day, (byDay.get(day) ?? 0) + 1);
  }
  let running = 0;
  return [...byDay.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([day, count]) => {
      running += count;
      return { day, total: running };
    });
}

export function deriveInsights(rows: MemoryDetail[]): MemoryInsights {
  const totals: MemoryTotals = {
    totalMemories: rows.length,
    permanentCount: rows.filter((m) => m.memoryType === "permanent").length,
    workingCount: rows.filter((m) => m.memoryType === "working").length,
    learnedCount: rows.filter((m) => m.memoryType === "learned").length,
    averageImportanceScore:
      rows.length === 0
        ? 0
        : rows.reduce((sum, m) => sum + m.importanceScore, 0) / rows.length,
  };

  const distribution: DistributionSlice[] = MEMORY_TYPES.map((type) =>
    slice(
      MEMORY_TYPE_LABEL[type],
      rows.filter((m) => m.memoryType === type).length,
      rows.length
    )
  ).filter((entry) => entry.count > 0);

  const owners = deriveOwners(rows);
  const topEmployees = owners
    .map((owner) =>
      slice(
        owner.employeeName,
        rows.filter((m) => m.owner.employeeId === owner.employeeId).length,
        rows.length
      )
    )
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.count - a.count);

  const collectionCount = rows.length;
  return {
    totals,
    distribution,
    growth: growthSeries(rows),
    collectionUsage: collectionCount
      ? [slice(COLLECTION_LABEL[DEFAULT_COLLECTION], collectionCount, collectionCount)]
      : [],
    kinds: rows.length ? [slice("Knowledge", rows.length, rows.length)] : [],
    languages: rows.length ? [slice(LANGUAGE_LABEL[DEFAULT_LANGUAGE], rows.length, rows.length)] : [],
    topEmployees,
    recentChanges: deriveTimeline(rows, null).slice(0, 6),
    totalSizeBytes: rows.reduce((sum, m) => sum + m.sizeBytes, 0),
  };
}

// --- Import (pure, client-side; nothing uploads) -------------------------

const baseName = (name: string): string => name.replace(/\.[^.]+$/, "");

function kindForType(type: ImportType | null): MemoryKind {
  switch (type) {
    case "json":
    case "csv":
      return "artifact";
    default:
      return "document";
  }
}

export function validateImportFiles(
  files: { name: string; sizeBytes: number }[],
  existingTitles: string[]
): ImportCandidate[] {
  const titles = new Set(existingTitles.map((t) => t.toLowerCase()));
  return files.map((file, index) => {
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    const type = (SUPPORTED_IMPORT_TYPES as readonly string[]).includes(extension)
      ? (extension as ImportType)
      : null;

    const issues: ImportIssue[] = [];
    if (type === null) {
      issues.push({
        level: "error",
        message: `“${extension || "no extension"}” isn't a type we can read. Supported: ${SUPPORTED_IMPORT_TYPES.join(", ")}.`,
      });
    }
    if (file.sizeBytes > MAX_IMPORT_BYTES) {
      issues.push({ level: "error", message: "Larger than the 5 MB limit." });
    }
    if (file.sizeBytes === 0) {
      issues.push({ level: "error", message: "The file is empty." });
    }
    if (titles.has(baseName(file.name).toLowerCase())) {
      issues.push({
        level: "warning",
        message: "A memory with this title already exists. Importing adds a second one.",
      });
    }

    return {
      id: `imp_${index + 1}`,
      name: file.name,
      sizeBytes: file.sizeBytes,
      type,
      issues,
      preview: {
        title: baseName(file.name),
        kind: kindForType(type),
        collection: DEFAULT_COLLECTION,
        language: DEFAULT_LANGUAGE,
        excerpt: "The file isn't read in the browser — the platform ingests it.",
      },
    };
  });
}

export function summariseImport(candidates: ImportCandidate[]): ImportSummary {
  const accepted = candidates.filter((c) => !c.issues.some((i) => i.level === "error"));
  const rejected = candidates.length - accepted.length;
  return {
    accepted: accepted.length,
    rejected,
    totalBytes: accepted.reduce((sum, c) => sum + c.sizeBytes, 0),
    createdIds: [],
    note:
      accepted.length === 0
        ? "Nothing would be imported."
        : `${accepted.length} file${accepted.length === 1 ? "" : "s"} would become ${accepted.length === 1 ? "a memory" : "memories"}. Ingestion is the platform's — the browser uploads nothing here.`,
  };
}
