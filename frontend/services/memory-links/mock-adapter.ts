import {
  MemoryLinkError,
  type LinkedMemory,
  type MemoryLinksAdapter,
  type MemoryScope,
  type MemorySearchQuery,
} from "./types";

/**
 * Deterministic in-browser mock of the memory-integration seam. No network, no
 * clock, no randomness. Selected via `NEXT_PUBLIC_MEMORY_ADAPTER=mock` for
 * offline UI work; the choice is app-wide, so mock and real memory links are
 * never mixed in one view.
 *
 * It keeps a small roster of memories and an in-memory set of links, so attach
 * and detach are observable across a session without a backend. Nothing is
 * persisted — a reload starts from the fixtures.
 */

const LATENCY_MS = 250;
const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

const ROSTER: LinkedMemory[] = [
  {
    id: "mem_1",
    employeeId: "emp_atlas",
    employeeName: "Atlas",
    memoryType: "permanent",
    content: "Invoices are approved by finance before they are sent to a client.",
    importanceScore: 0.9,
    createdAt: "2026-06-01T09:00:00.000Z",
    title: "Invoices are approved by finance before they are sent to a client.",
  },
  {
    id: "mem_2",
    employeeId: "emp_atlas",
    employeeName: "Atlas",
    memoryType: "working",
    content: "The Q3 report is due on the last business day of the quarter.",
    importanceScore: 0.6,
    createdAt: "2026-06-14T12:00:00.000Z",
    title: "The Q3 report is due on the last business day of the quarter.",
  },
  {
    id: "mem_3",
    employeeId: "emp_nova",
    employeeName: "Nova",
    memoryType: "learned",
    content: "This client prefers short, bulleted status updates over prose.",
    importanceScore: 0.4,
    createdAt: "2026-06-20T15:30:00.000Z",
    title: "This client prefers short, bulleted status updates over prose.",
  },
];

const key = (scope: MemoryScope, parentId: string) => `${scope}:${parentId}`;

export class MockMemoryLinksAdapter implements MemoryLinksAdapter {
  // parent → ordered list of memory ids it references.
  private readonly links = new Map<string, string[]>();

  async list(scope: MemoryScope, parentId: string): Promise<LinkedMemory[]> {
    await delay();
    const ids = this.links.get(key(scope, parentId)) ?? [];
    return ids
      .map((id) => ROSTER.find((m) => m.id === id))
      .filter((m): m is LinkedMemory => Boolean(m));
  }

  async attach(
    scope: MemoryScope,
    parentId: string,
    memoryId: string
  ): Promise<LinkedMemory> {
    await delay();
    const memory = ROSTER.find((m) => m.id === memoryId);
    if (!memory) throw new MemoryLinkError("not_found", "That memory doesn't exist.");
    const k = key(scope, parentId);
    const ids = this.links.get(k) ?? [];
    if (!ids.includes(memoryId)) {
      this.links.set(k, [...ids, memoryId]);
    }
    return memory;
  }

  async detach(scope: MemoryScope, parentId: string, memoryId: string): Promise<void> {
    await delay();
    const k = key(scope, parentId);
    const ids = this.links.get(k) ?? [];
    if (!ids.includes(memoryId)) {
      throw new MemoryLinkError("not_found", "That memory isn't linked here.");
    }
    this.links.set(k, ids.filter((id) => id !== memoryId));
  }

  async search(query: MemorySearchQuery): Promise<LinkedMemory[]> {
    await delay();
    const term = query.keyword.trim().toLowerCase();
    return ROSTER.filter((memory) => {
      if (query.memoryType !== "ALL" && memory.memoryType !== query.memoryType) return false;
      if (memory.importanceScore < query.minImportance) return false;
      if (!term) return true;
      return memory.content.toLowerCase().includes(term);
    });
  }
}
