import { describe, expect, it } from "vitest";
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
  validateImportFiles,
  type UserMemoryRow,
} from "./mapping";
import { EMPTY_SEARCH } from "./types";

/**
 * The Memory workspace's real ↔ workspace mapping (Sprint 23). The Memory Engine
 * stores a flat record, so these prove that (a) real columns map faithfully, (b)
 * projections are honest neutrals rather than invented, and (c) every aggregate
 * surface is derived consistently from those real records.
 */

const row = (over: Partial<UserMemoryRow> = {}): UserMemoryRow => ({
  id: "m1",
  employee_id: "e1",
  employee_name: "Ada",
  memory_type: "permanent",
  content: "The launch date is set.\nMore detail here.",
  importance_score: 0.8,
  created_at: "2026-07-01T10:00:00Z",
  ...over,
});

describe("toMemoryDetail", () => {
  it("maps the real columns faithfully", () => {
    const d = toMemoryDetail(row());
    expect(d.id).toBe("m1");
    expect(d.memoryType).toBe("permanent");
    expect(d.owner).toEqual({ employeeId: "e1", employeeName: "Ada" });
    expect(d.importanceScore).toBe(0.8);
    expect(d.content).toContain("launch date");
    // Title is the first non-empty line — a real derivation, not a fixture.
    expect(d.title).toBe("The launch date is set.");
    // Size is the real UTF-8 byte length.
    expect(d.sizeBytes).toBe(new TextEncoder().encode(row().content).length);
  });

  it("keeps projections neutral rather than invented", () => {
    const d = toMemoryDetail(row());
    expect(d.tags).toEqual([]);
    expect(d.collection).toBe("general");
    expect(d.language).toBe("en");
    expect(d.status).toBe("active");
    expect(d.linkedWorkflows).toEqual([]);
    expect(d.usage.recallCount).toBe(0);
  });

  it("defaults an unknown memory_type to learned", () => {
    expect(toMemoryDetail(row({ memory_type: "weird" })).memoryType).toBe("learned");
  });
});

describe("applyFacets", () => {
  const rows = [
    toMemoryDetail(row({ id: "a", employee_id: "e1", created_at: "2026-07-01T00:00:00Z" })),
    toMemoryDetail(row({ id: "b", employee_id: "e2", employee_name: "Bo", created_at: "2026-07-10T00:00:00Z" })),
  ].map(toSummary);

  it("narrows by owner", () => {
    const out = applyFacets(rows, { ...EMPTY_SEARCH, ownerId: "e2" });
    expect(out.map((m) => m.id)).toEqual(["b"]);
  });

  it("narrows by created-date window", () => {
    const out = applyFacets(rows, { ...EMPTY_SEARCH, fromDate: "2026-07-05", toDate: "2026-07-31" });
    expect(out.map((m) => m.id)).toEqual(["b"]);
  });

  it("returns everything when unfiltered", () => {
    expect(applyFacets(rows, EMPTY_SEARCH)).toHaveLength(2);
  });
});

describe("derived aggregates", () => {
  const rows = [
    toMemoryDetail(row({ id: "a", memory_type: "permanent", employee_id: "e1", employee_name: "Ada" })),
    toMemoryDetail(row({ id: "b", memory_type: "working", employee_id: "e1", employee_name: "Ada" })),
    toMemoryDetail(row({ id: "c", memory_type: "permanent", employee_id: "e2", employee_name: "Bo" })),
  ];

  it("counts owners uniquely", () => {
    expect(deriveOwners(rows).map((o) => o.employeeId)).toEqual(["e1", "e2"]);
  });

  it("totals insights from the real records", () => {
    const insights = deriveInsights(rows);
    expect(insights.totals.totalMemories).toBe(3);
    expect(insights.totals.permanentCount).toBe(2);
    expect(insights.totals.workingCount).toBe(1);
    expect(insights.topEmployees[0]).toMatchObject({ label: "Ada", count: 2 });
  });

  it("rolls every memory into the one collection", () => {
    const [general] = deriveCollections(rows);
    expect(general.count).toBe(3);
  });

  it("builds an OWNS graph linking employees to their memories", () => {
    const graph = deriveGraph(rows);
    expect(graph.nodes.filter((n) => n.kind === "employee")).toHaveLength(2);
    expect(graph.nodes.filter((n) => n.kind === "memory")).toHaveLength(3);
    expect(graph.edges.every((e) => e.relationship === "OWNS")).toBe(true);
  });

  it("derives a newest-first CREATED timeline", () => {
    const events = deriveTimeline(rows, null);
    expect(events).toHaveLength(3);
    expect(events.every((e) => e.kind === "CREATED")).toBe(true);
  });
});

describe("import validation (pure, client-side)", () => {
  it("rejects an unknown type and accepts a known one", () => {
    const candidates = validateImportFiles(
      [
        { name: "notes.md", sizeBytes: 10 },
        { name: "photo.png", sizeBytes: 10 },
      ],
      []
    );
    expect(candidates[0].issues).toHaveLength(0);
    expect(candidates[1].issues.some((i) => i.level === "error")).toBe(true);

    const summary = summariseImport(candidates);
    expect(summary.accepted).toBe(1);
    expect(summary.rejected).toBe(1);
    // Nothing is uploaded here — no ids are created.
    expect(summary.createdIds).toEqual([]);
  });
});
