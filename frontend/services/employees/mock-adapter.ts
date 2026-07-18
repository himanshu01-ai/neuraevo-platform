import { ACTIVITY, CAPABILITY_AVAILABILITY_CATALOG, EMPLOYEES, TEMPLATES } from "./fixtures";
import type { EmployeesBackendSupport } from "./support";
import {
  EMPLOYEE_CAPABILITIES,
  EMPLOYEE_PERMISSIONS,
  EmployeeError,
  PERMISSION_DEFAULT_LEVEL,
  PERMISSION_REQUIRES,
  type EmployeeActivityEvent,
  type EmployeeCapability,
  type EmployeeCapabilityState,
  type EmployeeDetail,
  type EmployeeDraft,
  type EmployeePermission,
  type EmployeeSummary,
  type EmployeeTemplate,
  type EmployeeTemplateSummary,
  type EmployeesAdapter,
} from "./types";

/**
 * Deterministic in-browser mock of an employee backend. No network, no clock, no
 * randomness. Writes go to localStorage to simulate server persistence so a new
 * employee survives a reload — the same approach `MockWorkflowsAdapter` uses
 * (Sprint 17.5) and `MockAuthAdapter` before it (Sprint 17.2).
 *
 * This mock stores descriptions only. It never runs an employee, never invokes a
 * capability, and never derives a status from anything but the fixtures and what
 * the user saved. Statuses move only when the user asks for it (archive), never
 * on their own.
 */

const STORE_KEY = "neuraevo.mock.employees";
const ACTIVITY_KEY = "neuraevo.mock.employees.activity";
const LATENCY_MS = 350;

const delay = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));

/** Structured clone via JSON — fixtures and stored rows are plain data. */
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

type ActivityLog = Record<string, EmployeeActivityEvent[]>;

function readStore(): EmployeeDetail[] {
  const seed = () => copy(EMPLOYEES) as EmployeeDetail[];
  if (typeof window === "undefined") return seed();
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (!raw) return seed();
    const parsed = JSON.parse(raw) as EmployeeDetail[];
    return Array.isArray(parsed) ? parsed : seed();
  } catch {
    return seed();
  }
}

function writeStore(rows: EmployeeDetail[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORE_KEY, JSON.stringify(rows));
  } catch {
    /* quota or private mode — the change simply doesn't persist */
  }
}

function readActivity(): ActivityLog {
  const seed = () => copy(ACTIVITY) as ActivityLog;
  if (typeof window === "undefined") return seed();
  try {
    const raw = window.localStorage.getItem(ACTIVITY_KEY);
    if (!raw) return seed();
    const parsed = JSON.parse(raw) as ActivityLog;
    return parsed && typeof parsed === "object" ? parsed : seed();
  } catch {
    return seed();
  }
}

function writeActivity(log: ActivityLog) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ACTIVITY_KEY, JSON.stringify(log));
  } catch {
    /* quota or private mode — the event simply doesn't persist */
  }
}

/**
 * Appends one event to an employee's history. History is append-only: an event
 * records that something happened, so it is never rewritten or removed.
 */
function logEvent(id: string, kind: EmployeeActivityEvent["kind"], summary: string) {
  const log = readActivity();
  const events = log[id] ?? [];
  const sequence = events.reduce((max, e) => Math.max(max, e.sequence), 0) + 1;
  log[id] = [{ id: `act_${id}_${sequence}`, kind, summary, sequence }, ...events];
  writeActivity(log);
}

const toSummary = (detail: EmployeeDetail): EmployeeSummary => ({
  id: detail.id,
  name: detail.name,
  role: detail.role,
  customRole: detail.customRole,
  description: detail.description,
  status: detail.status,
  health: detail.health,
  accent: detail.accent,
  glyph: detail.glyph,
  capabilities: detail.capabilities,
  assignedWorkflows: detail.assignedWorkflows,
  lastActivity: detail.lastActivity,
  sequence: detail.sequence,
});

const toTemplateSummary = (template: EmployeeTemplate): EmployeeTemplateSummary => ({
  id: template.id,
  name: template.name,
  description: template.description,
  category: template.category,
  role: template.role,
  accent: template.accent,
  glyph: template.glyph,
  capabilities: template.capabilities,
});

/** Deterministic id from the existing rows — no randomness, no timestamps. */
function nextId(rows: EmployeeDetail[], prefix: string): string {
  let n = rows.length + 1;
  while (rows.some((r) => r.id === `${prefix}_${n}`)) n++;
  return `${prefix}_${n}`;
}

const nextSequence = (rows: EmployeeDetail[]): number =>
  rows.reduce((max, r) => Math.max(max, r.sequence), 0) + 1;

export class MockEmployeesAdapter implements EmployeesAdapter {
  /** The mock simulates the whole surface, so nothing is gated. */
  readonly support: EmployeesBackendSupport = {
    update: true,
    archive: true,
    remove: true,
    activity: true,
    capabilities: true,
    assignments: true,
    permissions: true,
    configuration: true,
    appearance: true,
  };

  async list(): Promise<EmployeeSummary[]> {
    await delay();
    return readStore()
      .slice()
      .sort((a, b) => b.sequence - a.sequence)
      .map(toSummary);
  }

  async detail(id: string): Promise<EmployeeDetail> {
    await delay();
    const found = readStore().find((e) => e.id === id);
    if (!found) throw new EmployeeError("not_found", "That employee doesn't exist.");
    return copy(found);
  }

  async save(draft: EmployeeDraft): Promise<EmployeeDetail> {
    await delay();
    if (!draft.name.trim()) throw new EmployeeError("invalid_draft", "An employee needs a name.");

    const rows = readStore();
    const index = draft.id ? rows.findIndex((e) => e.id === draft.id) : -1;
    const existing = index >= 0 ? rows[index] : undefined;

    const saved: EmployeeDetail = {
      id: existing?.id ?? nextId(rows, "emp"),
      name: draft.name.trim(),
      role: draft.role,
      customRole: draft.customRole.trim(),
      description: draft.description.trim(),
      // A description is authored; presence is the platform's to report. A new
      // employee is UNKNOWN rather than AVAILABLE — nothing has observed it yet.
      status: existing?.status ?? "UNKNOWN",
      health: existing?.health ?? "UNKNOWN",
      accent: draft.accent,
      glyph: draft.glyph,
      capabilities: [...draft.capabilities],
      assignedWorkflows: existing?.assignedWorkflows ?? 0,
      lastActivity: existing?.lastActivity ?? "Created, not yet started",
      sequence: existing?.sequence ?? nextSequence(rows),
      behaviorSummary: draft.behaviorSummary.trim(),
      configuration: copy(draft.configuration),
      // Permissions follow the capabilities that were granted; an employee can
      // never hold a permission for a capability it doesn't have.
      permissions: reconcilePermissions(existing, draft),
      assignments: existing?.assignments ?? { workflows: [], currentTask: null, queue: [] },
      memory: existing?.memory ?? { total: 0, categories: [], latest: null },
    };

    if (index >= 0) rows[index] = saved;
    else rows.push(saved);
    writeStore(rows);

    if (existing) logEvent(saved.id, "UPDATED", `${saved.name} was updated`);
    else logEvent(saved.id, "CREATED", `${saved.name} was created`);

    return copy(saved);
  }

  async duplicate(id: string): Promise<EmployeeDetail> {
    await delay();
    const rows = readStore();
    const source = rows.find((e) => e.id === id);
    if (!source) throw new EmployeeError("not_found", "That employee doesn't exist.");

    const clone: EmployeeDetail = {
      ...copy(source),
      id: nextId(rows, "emp"),
      name: `${source.name} (copy)`,
      // A copy inherits the description, never the standing: it has done nothing
      // and is assigned to nothing.
      status: "UNKNOWN",
      health: "UNKNOWN",
      assignedWorkflows: 0,
      lastActivity: "Created, not yet started",
      sequence: nextSequence(rows),
      assignments: { workflows: [], currentTask: null, queue: [] },
      memory: { total: 0, categories: [], latest: null },
    };
    rows.push(clone);
    writeStore(rows);
    logEvent(clone.id, "CREATED", `${clone.name} was created from ${source.name}`);
    return copy(clone);
  }

  /**
   * Archiving takes an employee out of service without destroying it — the one
   * status this layer sets, because the user asked for it directly.
   */
  async archive(id: string): Promise<EmployeeDetail> {
    await delay();
    const rows = readStore();
    const index = rows.findIndex((e) => e.id === id);
    const existing = index >= 0 ? rows[index] : undefined;
    if (!existing) throw new EmployeeError("not_found", "That employee doesn't exist.");

    const archived: EmployeeDetail = {
      ...copy(existing),
      status: "OFFLINE",
      lastActivity: "Archived by you",
      assignments: { workflows: [], currentTask: null, queue: [] },
      assignedWorkflows: 0,
    };
    rows[index] = archived;
    writeStore(rows);
    logEvent(id, "PAUSED", `${archived.name} was archived`);
    return copy(archived);
  }

  async remove(id: string): Promise<void> {
    await delay();
    writeStore(readStore().filter((e) => e.id !== id));
    const log = readActivity();
    delete log[id];
    writeActivity(log);
  }

  async activity(id: string): Promise<EmployeeActivityEvent[]> {
    await delay();
    const events = readActivity()[id] ?? [];
    return copy(events).sort((a, b) => b.sequence - a.sequence);
  }

  /**
   * Every capability the platform offers, marked with whether this employee
   * holds it. The full list is returned — a capability the employee lacks is
   * still worth showing, because granting it is the next thing you'd do.
   */
  async capabilities(id: string): Promise<EmployeeCapabilityState[]> {
    await delay();
    const found = readStore().find((e) => e.id === id);
    if (!found) throw new EmployeeError("not_found", "That employee doesn't exist.");
    const held = new Set(found.capabilities);

    return EMPLOYEE_CAPABILITIES.map((capability) => ({
      capability,
      status: held.has(capability) ? "GRANTED" : "NOT_GRANTED",
      availability: CAPABILITY_AVAILABILITY_CATALOG[capability],
    }));
  }

  async templates(): Promise<EmployeeTemplateSummary[]> {
    await delay();
    return TEMPLATES.map(toTemplateSummary);
  }

  async template(id: string): Promise<EmployeeTemplate> {
    await delay();
    const found = TEMPLATES.find((t) => t.id === id);
    if (!found) throw new EmployeeError("not_found", "That template doesn't exist.");
    return copy(found);
  }
}

/**
 * Keeps permissions consistent with the granted capabilities. A level the user
 * already chose is kept; a capability that was just revoked drops back to
 * BLOCKED; a newly granted one takes the conservative default for that
 * permission. Access is never widened on the user's behalf.
 */
function reconcilePermissions(
  existing: EmployeeDetail | undefined,
  draft: EmployeeDraft
): EmployeePermission[] {
  const held = new Set<EmployeeCapability>(draft.capabilities);

  return EMPLOYEE_PERMISSIONS.map((id) => {
    if (!held.has(PERMISSION_REQUIRES[id])) return { id, level: "BLOCKED" };

    const previous = existing?.permissions.find((p) => p.id === id);
    if (previous && previous.level !== "BLOCKED") return { id, level: previous.level };
    return { id, level: PERMISSION_DEFAULT_LEVEL[id] };
  });
}
