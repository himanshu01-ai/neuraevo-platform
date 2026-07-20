import { TEMPLATES, WORKFLOWS } from "./fixtures";
import {
  WorkflowError,
  type WorkflowDetail,
  type WorkflowDraft,
  type WorkflowRun,
  type WorkflowSummary,
  type WorkflowTemplate,
  type WorkflowTemplateSummary,
  type WorkflowsAdapter,
} from "./types";

/**
 * Deterministic in-browser mock of a workflow backend. No network, no clock, no
 * randomness. Saves are written to localStorage to simulate server persistence
 * so a draft survives a reload — the same approach `MockAuthAdapter` uses for
 * its session (Sprint 17.2).
 *
 * This mock stores structure only. It never runs a workflow, never invokes a
 * capability, and never derives a status from anything but the fixtures and
 * what the user saved. `execute` simulates a result rather than producing one —
 * see its own note.
 */

const STORE_KEY = "neuraevo.mock.workflows";
const LATENCY_MS = 350;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

/** Structured clone via JSON — fixtures and stored rows are plain data. */
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function readStore(): WorkflowDetail[] {
  if (typeof window === "undefined") return copy(WORKFLOWS as unknown as WorkflowDetail[]);
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (!raw) return copy(WORKFLOWS as unknown as WorkflowDetail[]);
    const parsed = JSON.parse(raw) as WorkflowDetail[];
    return Array.isArray(parsed) ? parsed : copy(WORKFLOWS as unknown as WorkflowDetail[]);
  } catch {
    return copy(WORKFLOWS as unknown as WorkflowDetail[]);
  }
}

function writeStore(rows: WorkflowDetail[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORE_KEY, JSON.stringify(rows));
  } catch {
    /* quota or private mode — the draft simply doesn't persist */
  }
}

const toSummary = (detail: WorkflowDetail): WorkflowSummary => ({
  id: detail.id,
  name: detail.name,
  description: detail.description,
  lifecycle: detail.lifecycle,
  nodeCount: detail.graph.nodes.length,
  sequence: detail.sequence,
});

const toTemplateSummary = (template: WorkflowTemplate): WorkflowTemplateSummary => ({
  id: template.id,
  name: template.name,
  description: template.description,
  category: template.category,
  nodeCount: template.nodeCount,
});

/** Deterministic id from the existing rows — no randomness, no timestamps. */
function nextId(rows: WorkflowDetail[], prefix: string): string {
  let n = rows.length + 1;
  while (rows.some((r) => r.id === `${prefix}_${n}`)) n++;
  return `${prefix}_${n}`;
}

const nextSequence = (rows: WorkflowDetail[]): number =>
  rows.reduce((max, r) => Math.max(max, r.sequence), 0) + 1;

export class MockWorkflowsAdapter implements WorkflowsAdapter {
  async list(): Promise<WorkflowSummary[]> {
    await delay();
    return readStore()
      .slice()
      .sort((a, b) => b.sequence - a.sequence)
      .map(toSummary);
  }

  async detail(id: string): Promise<WorkflowDetail> {
    await delay();
    const found = readStore().find((w) => w.id === id);
    if (!found) throw new WorkflowError("not_found", "That workflow doesn't exist.");
    return copy(found);
  }

  async save(draft: WorkflowDraft): Promise<WorkflowDetail> {
    await delay();
    const rows = readStore();
    const index = rows.findIndex((w) => w.id === draft.id);
    const existing = index >= 0 ? rows[index] : undefined;

    const saved: WorkflowDetail = {
      id: existing ? existing.id : nextId(rows, "wfl"),
      name: draft.name,
      description: draft.description,
      // A new workflow starts as a DRAFT; an existing one keeps its lifecycle,
      // since saving edits structure and never changes the authoring state.
      lifecycle: existing ? existing.lifecycle : "DRAFT",
      nodeCount: draft.graph.nodes.length,
      sequence: existing ? existing.sequence : nextSequence(rows),
      graph: copy(draft.graph),
      settings: copy(draft.settings),
    };

    if (index >= 0) rows[index] = saved;
    else rows.push(saved);
    writeStore(rows);
    return copy(saved);
  }

  async duplicate(id: string): Promise<WorkflowDetail> {
    await delay();
    const rows = readStore();
    const source = rows.find((w) => w.id === id);
    if (!source) throw new WorkflowError("not_found", "That workflow doesn't exist.");

    const clone: WorkflowDetail = {
      ...copy(source),
      id: nextId(rows, "wfl"),
      name: `${source.name} (copy)`,
      // A copy has not been reviewed, so it is born a draft regardless of the
      // source's lifecycle — matching the backend.
      lifecycle: "DRAFT",
      sequence: nextSequence(rows),
    };
    rows.push(clone);
    writeStore(rows);
    return copy(clone);
  }

  /** Publish a draft. Mirrors the backend's `draft ⇄ published` transition. */
  async publish(id: string): Promise<WorkflowDetail> {
    return this.setLifecycle(id, "PUBLISHED");
  }

  async unpublish(id: string): Promise<WorkflowDetail> {
    return this.setLifecycle(id, "DRAFT");
  }

  private async setLifecycle(
    id: string,
    lifecycle: WorkflowDetail["lifecycle"],
  ): Promise<WorkflowDetail> {
    await delay();
    const rows = readStore();
    const index = rows.findIndex((w) => w.id === id);
    const existing = index >= 0 ? rows[index] : undefined;
    if (!existing) throw new WorkflowError("not_found", "That workflow doesn't exist.");
    if (existing.lifecycle === "ARCHIVED") {
      throw new WorkflowError("invalid_import", "Restore this workflow before changing it.");
    }

    const updated: WorkflowDetail = { ...copy(existing), lifecycle };
    rows[index] = updated;
    writeStore(rows);
    return copy(updated);
  }

  /** Archiving retires a workflow without destroying it. */
  async archive(id: string): Promise<WorkflowDetail> {
    await delay();
    const rows = readStore();
    const index = rows.findIndex((w) => w.id === id);
    const existing = index >= 0 ? rows[index] : undefined;
    if (!existing) throw new WorkflowError("not_found", "That workflow doesn't exist.");
    if (existing.lifecycle === "ARCHIVED") {
      throw new WorkflowError("invalid_import", "That workflow is already archived.");
    }

    const archived: WorkflowDetail = { ...copy(existing), lifecycle: "ARCHIVED" };
    rows[index] = archived;
    writeStore(rows);
    return copy(archived);
  }

  /** Restoring returns it to the bench — `DRAFT`, never straight to published. */
  async restore(id: string): Promise<WorkflowDetail> {
    await delay();
    const rows = readStore();
    const index = rows.findIndex((w) => w.id === id);
    const existing = index >= 0 ? rows[index] : undefined;
    if (!existing) throw new WorkflowError("not_found", "That workflow doesn't exist.");
    if (existing.lifecycle !== "ARCHIVED") {
      throw new WorkflowError("invalid_import", "Only an archived workflow can be restored.");
    }

    const restored: WorkflowDetail = { ...copy(existing), lifecycle: "DRAFT" };
    rows[index] = restored;
    writeStore(rows);
    return copy(restored);
  }

  async remove(id: string): Promise<void> {
    await delay();
    const rows = readStore().filter((w) => w.id !== id);
    writeStore(rows);
  }

  /**
   * A simulated run, so the result UI can be worked on offline.
   *
   * It enforces the one rule this adapter already owns — only a published
   * workflow runs — and then reports every step as completed. It does not
   * translate the graph, does not know which node kinds the platform can
   * execute, and never invokes anything: those are the engine's to decide, and
   * copying that table here would be a second answer to the same question.
   *
   * So translation failures and step failures can only be seen against the real
   * backend. That is the point of a mock, not a gap in it.
   */
  async execute(id: string): Promise<WorkflowRun> {
    await delay();
    const found = readStore().find((w) => w.id === id);
    if (!found) throw new WorkflowError("not_found", "That workflow doesn't exist.");
    if (found.lifecycle === "ARCHIVED") {
      throw new WorkflowError(
        "invalid_import",
        "An archived workflow can't be run. Restore it first.",
      );
    }
    if (found.lifecycle !== "PUBLISHED") {
      throw new WorkflowError(
        "invalid_import",
        "Only a published workflow can be run. Publish it first.",
      );
    }
    if (found.graph.nodes.length === 0) {
      throw new WorkflowError(
        "invalid_import",
        "This workflow has no steps to run. Add at least one before executing it.",
      );
    }

    return {
      workflowId: found.id,
      status: "COMPLETED",
      completedStepCount: found.graph.nodes.length,
      totalStepCount: found.graph.nodes.length,
      failedStepId: null,
      steps: found.graph.nodes.map((node) => ({
        id: node.id,
        capability: node.kind,
        status: "COMPLETED",
        outputs: [{ key: "simulated", value: "This run was simulated by the mock adapter." }],
      })),
      error: null,
    };
  }

  async templates(): Promise<WorkflowTemplateSummary[]> {
    await delay();
    return TEMPLATES.map(toTemplateSummary);
  }

  async template(id: string): Promise<WorkflowTemplate> {
    await delay();
    const found = TEMPLATES.find((t) => t.id === id);
    if (!found) throw new WorkflowError("not_found", "That template doesn't exist.");
    return copy(found);
  }
}
