import { dateValue, isoDay } from "@/utils/format";
import { COLLECTION_DESCRIPTIONS, GRAPH, MEMORIES, OWNER_LIST, TAGS, TIMELINE } from "./fixtures";
import {
  COLLECTIONS,
  COLLECTION_LABEL,
  LANGUAGES,
  LANGUAGE_LABEL,
  MAX_IMPORT_BYTES,
  MEMORY_KINDS,
  MEMORY_TYPES,
  MEMORY_TYPE_LABEL,
  MemoryError,
  SUPPORTED_IMPORT_TYPES,
  type Collection,
  type CollectionSummary,
  type DistributionSlice,
  type EmployeeLink,
  type GrowthPoint,
  type ImportCandidate,
  type ImportIssue,
  type ImportSummary,
  type ImportType,
  type KnowledgeGraph,
  type MemoryAdapter,
  type MemoryDetail,
  type MemoryInsights,
  type MemoryKind,
  type MemorySummary,
  type MemoryTotals,
  type SearchQuery,
  type TimelineEvent,
} from "./types";

/**
 * Deterministic in-browser mock of the Memory Engine. No network, no clock, no
 * randomness — and, deliberately, no retrieval machinery of any kind.
 *
 * ## What "mock search" means here
 *
 * `list` filters. It does not rank, embed, or score relevance: a keyword match
 * is `includes` over the title, summary, content and tags, and the results come
 * back in the order the fixtures declare. There is no vector, no index, and no
 * similarity — the real engine's pgvector work is the backend's, and pretending
 * to do it here would produce an ordering that nothing behind it could
 * reproduce.
 *
 * The frozen API already filters `memory_type` and `min_importance` server-side
 * and paginates with `limit`/`offset`. `list` takes the whole `SearchQuery` so
 * Sprint 17.9 can push those facets down the wire without touching a caller.
 *
 * Unlike the other mocks in this app, this one **does not write to
 * localStorage**: this sprint visualises memory and changes nothing about it, so
 * there is no user edit to persist.
 */

const LATENCY_MS = 350;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

/** Structured clone via JSON — fixtures are plain data. */
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

const toSummary = (memory: MemoryDetail): MemorySummary => {
  const { content: _content, linkedEmployees: _le, linkedWorkflows: _lw, usage: _usage, ...summary } = memory;
  return summary;
};

/** A slice with its share of the whole. `ratio` is 0 when there's nothing. */
const slice = (label: string, count: number, total: number): DistributionSlice => ({
  label,
  count,
  ratio: total === 0 ? 0 : count / total,
});

/** Counts by key, in the order the keys are given — never alphabetical drift. */
function distribution<T extends string>(
  keys: readonly T[],
  label: (key: T) => string,
  pick: (memory: MemoryDetail) => T,
  rows: readonly MemoryDetail[]
): DistributionSlice[] {
  return keys
    .map((key) => slice(label(key), rows.filter((m) => pick(m) === key).length, rows.length))
    .filter((entry) => entry.count > 0);
}

export class MockMemoryAdapter implements MemoryAdapter {
  /**
   * Filtering only — every facet is an exact match except `keyword`, which is a
   * plain substring scan. Nothing here is ranked.
   */
  async list(query: SearchQuery): Promise<MemorySummary[]> {
    await delay();
    const term = query.keyword.trim().toLowerCase();
    const from = query.fromDate ? query.fromDate : null;
    const to = query.toDate ? query.toDate : null;

    return MEMORIES.filter((memory) => {
      if (query.collection !== "ALL" && memory.collection !== query.collection) return false;
      if (query.ownerId !== "ALL" && memory.owner.employeeId !== query.ownerId) return false;
      if (query.language !== "ALL" && memory.language !== query.language) return false;
      if (query.kind !== "ALL" && memory.kind !== query.kind) return false;
      if (query.memoryType !== "ALL" && memory.memoryType !== query.memoryType) return false;
      if (query.status !== "ALL" && memory.status !== query.status) return false;
      // The API's own `min_importance >= value` semantics, kept identical here.
      if (memory.importanceScore < query.minImportance) return false;

      // Every selected tag must be present — narrowing, not widening.
      if (query.tags.length > 0 && !query.tags.every((tag) => memory.tags.includes(tag))) return false;

      // Dates compare as ISO days, so a time zone can't move a memory across a
      // boundary the user picked.
      const day = isoDay(memory.createdAt);
      if (from && day < from) return false;
      if (to && day > to) return false;

      if (!term) return true;
      const haystack = [memory.title, memory.summary, memory.content, memory.tags.join(" ")]
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    }).map(toSummary);
  }

  async detail(id: string): Promise<MemoryDetail> {
    await delay();
    const found = MEMORIES.find((m) => m.id === id);
    if (!found) throw new MemoryError("not_found", "That memory doesn't exist.");
    return copy(found);
  }

  async collections(): Promise<CollectionSummary[]> {
    await delay();
    return COLLECTIONS.map((collection) => {
      const rows = MEMORIES.filter((m) => m.collection === collection);
      // A custom shelf shows the name the user gave it, not the word "Custom".
      const custom = rows.find((m) => m.customCollection.trim() !== "");
      return {
        collection,
        name:
          collection === "custom" && custom
            ? custom.customCollection
            : COLLECTION_LABEL[collection],
        description: COLLECTION_DESCRIPTIONS[collection] ?? "",
        count: rows.length,
        sizeBytes: rows.reduce((sum, m) => sum + m.sizeBytes, 0),
      };
    });
  }

  /** One memory's history, or the whole workspace's when `memoryId` is null. */
  async timeline(memoryId: string | null): Promise<TimelineEvent[]> {
    await delay();
    const rows = memoryId === null ? TIMELINE : TIMELINE.filter((e) => e.memoryId === memoryId);
    return copy(rows as TimelineEvent[]).sort((a, b) => dateValue(b.at) - dateValue(a.at));
  }

  async graph(): Promise<KnowledgeGraph> {
    await delay();
    return copy(GRAPH);
  }

  async insights(): Promise<MemoryInsights> {
    await delay();
    const rows = MEMORIES;

    // Mirrors MemoryStatsResponse field for field — this is the one part of the
    // insights a real endpoint already answers.
    const totals: MemoryTotals = {
      totalMemories: rows.length,
      permanentCount: rows.filter((m) => m.memoryType === "permanent").length,
      workingCount: rows.filter((m) => m.memoryType === "working").length,
      learnedCount: rows.filter((m) => m.memoryType === "learned").length,
      averageImportanceScore:
        rows.length === 0 ? 0 : rows.reduce((sum, m) => sum + m.importanceScore, 0) / rows.length,
    };

    const topEmployees = OWNER_LIST.map((owner) =>
      slice(
        owner.employeeName,
        rows.filter((m) => m.linkedEmployees.some((l) => l.employeeId === owner.employeeId)).length,
        rows.length
      )
    )
      .filter((entry) => entry.count > 0)
      .sort((a, b) => b.count - a.count);

    return {
      totals,
      distribution: distribution(MEMORY_TYPES, (k) => MEMORY_TYPE_LABEL[k], (m) => m.memoryType, rows),
      growth: growthSeries(rows),
      collectionUsage: distribution(
        COLLECTIONS,
        (k) => COLLECTION_LABEL[k],
        (m) => m.collection,
        rows
      ),
      kinds: distribution(MEMORY_KINDS, (k) => titleCase(k), (m) => m.kind, rows),
      languages: distribution(LANGUAGES, (k) => LANGUAGE_LABEL[k], (m) => m.language, rows),
      topEmployees,
      recentChanges: copy(TIMELINE as TimelineEvent[])
        .sort((a, b) => dateValue(b.at) - dateValue(a.at))
        .slice(0, 6),
      totalSizeBytes: rows.reduce((sum, m) => sum + m.sizeBytes, 0),
    };
  }

  async owners(): Promise<EmployeeLink[]> {
    await delay();
    return copy(OWNER_LIST as EmployeeLink[]);
  }

  async tags(): Promise<string[]> {
    await delay();
    return [...TAGS];
  }

  /**
   * Checks staged files and reports what *would* happen. Nothing is read,
   * uploaded, or parsed — the preview is derived from the file's name and size,
   * which is all a drop event gives us without opening the file.
   */
  async validateImport(files: { name: string; sizeBytes: number }[]): Promise<ImportCandidate[]> {
    await delay();

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
      if (MEMORIES.some((m) => m.title.toLowerCase() === baseName(file.name).toLowerCase())) {
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
          collection: "general" as Collection,
          language: "en",
          excerpt: "The file isn't read in this sprint, so there's nothing to show yet.",
        },
      };
    });
  }

  /**
   * Reports the shape of an import. Creates nothing — `createdIds` is always
   * empty, and the note says so rather than letting a count imply otherwise.
   */
  async summariseImport(candidates: ImportCandidate[]): Promise<ImportSummary> {
    await delay();
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
          : `${accepted.length} file${accepted.length === 1 ? "" : "s"} would become ${accepted.length === 1 ? "a memory" : "memories"}. Nothing is uploaded in this sprint — the platform does the reading.`,
    };
  }
}

/** `"notes.md"` → `"notes"`. */
const baseName = (name: string): string => name.replace(/\.[^.]+$/, "");

const titleCase = (value: string): string => value.charAt(0).toUpperCase() + value.slice(1);

/** What an imported file would most likely become. Descriptive, not clever. */
function kindForType(type: ImportType | null): MemoryKind {
  switch (type) {
    case "md":
    case "txt":
    case "pdf":
    case "docx":
      return "document";
    case "json":
    case "csv":
      return "artifact";
    default:
      return "document";
  }
}

/**
 * Knowledge Growth: a running total of memories by the day they were created.
 *
 * Only days that actually saw a memory become steps — a series with an entry for
 * every empty day in between would be a chart of nothing happening. The total is
 * cumulative, so the line only ever climbs, which is what "growth" means here.
 */
function growthSeries(rows: readonly MemoryDetail[]): GrowthPoint[] {
  const byDay = new Map<string, number>();
  rows.forEach((memory) => {
    const day = isoDay(memory.createdAt);
    byDay.set(day, (byDay.get(day) ?? 0) + 1);
  });

  let running = 0;
  return [...byDay.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([day, count]) => {
      running += count;
      return { day, total: running };
    });
}
