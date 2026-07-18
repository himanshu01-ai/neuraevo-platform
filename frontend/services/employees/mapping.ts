import { z } from "zod";
import { DEFAULT_CONFIGURATION } from "./defaults";
import {
  EMPLOYEE_ACCENTS,
  EMPLOYEE_ROLES,
  type EmployeeAccent,
  type EmployeeDetail,
  type EmployeeDraft,
  type EmployeeGlyph,
  type EmployeeMemorySummary,
  type EmployeeRole,
  type EmployeeStatus,
  type EmployeeSummary,
} from "./types";

/**
 * Translation between the backend's employee contracts and this layer's
 * presentation models. The two never meet anywhere else: the adapter speaks
 * HTTP, the feature speaks `EmployeeSummary`/`EmployeeDetail`, and everything
 * in between happens here.
 *
 * The backend row is deliberately small — `name, role, description, language,
 * personality, status, created_at` — while the frontend model describes far
 * more. Fields with no backend counterpart are NOT invented here: they resolve
 * to explicit "nothing known" values (empty capability list, `UNKNOWN` health,
 * zero assignments) so the UI renders its real empty states. The only things
 * derived are presentation-only (accent, glyph), which the frontend has always
 * owned.
 */

// --- Backend wire schemas ------------------------------------------------
// Mirrors of backend/app/schemas/employee.py and memory_stats.py.

export const employeeResponseSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  name: z.string(),
  role: z.string(),
  description: z.string().nullable().optional(),
  language: z.string(),
  personality: z.string().nullable().optional(),
  status: z.string(),
  created_at: z.string(),
});

export type EmployeeResponse = z.infer<typeof employeeResponseSchema>;

export const memoryStatsResponseSchema = z.object({
  total_memories: z.number(),
  permanent_count: z.number(),
  working_count: z.number(),
  learned_count: z.number(),
  average_importance_score: z.number(),
});

export type MemoryStatsResponse = z.infer<typeof memoryStatsResponseSchema>;

// --- Role ----------------------------------------------------------------

/**
 * The backend stores `role` as free text, so the enum round-trips through it:
 * a known member is stored verbatim and read straight back, and anything else
 * becomes `CUSTOM` carrying the original string in `customRole`.
 */
const ROLE_SET = new Set<string>(EMPLOYEE_ROLES);

export function toRole(role: string): { role: EmployeeRole; customRole: string } {
  if (ROLE_SET.has(role) && role !== "CUSTOM") {
    return { role: role as EmployeeRole, customRole: "" };
  }
  return { role: "CUSTOM", customRole: role };
}

export function fromRole(role: EmployeeRole, customRole: string): string {
  if (role === "CUSTOM") return customRole.trim() || "CUSTOM";
  return role;
}

// --- Status --------------------------------------------------------------

/**
 * `Employee.status` is a free-form `String(50)` that today only ever holds the
 * model default, `"draft"`. Anything this layer doesn't recognise maps to
 * `UNKNOWN` rather than guessing — the employee's real standing is the
 * platform's to report, and the platform doesn't report it yet.
 */
const STATUS_BY_BACKEND_VALUE: Record<string, EmployeeStatus> = {
  draft: "UNKNOWN",
  available: "AVAILABLE",
  busy: "BUSY",
  working: "WORKING",
  paused: "PAUSED",
  offline: "OFFLINE",
  archived: "OFFLINE",
};

export function toStatus(status: string): EmployeeStatus {
  return STATUS_BY_BACKEND_VALUE[status.trim().toLowerCase()] ?? "UNKNOWN";
}

// --- Appearance ----------------------------------------------------------

/**
 * Accent and glyph are presentation, not data — the backend has never stored
 * them and the theme owns both. Deriving them from the id keeps an employee
 * looking the same on every device and across reloads, which a random or
 * fixed-default choice would not.
 */
export function toAccent(id: string): EmployeeAccent {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) | 0;
  return EMPLOYEE_ACCENTS[Math.abs(hash) % EMPLOYEE_ACCENTS.length] ?? "slate";
}

const GLYPH_BY_ROLE: Record<EmployeeRole, EmployeeGlyph> = {
  RESEARCH_ASSISTANT: "brain",
  SOFTWARE_ENGINEER: "code",
  DATA_ANALYST: "chart",
  PROJECT_MANAGER: "briefcase",
  CONTENT_WRITER: "pen",
  CUSTOMER_SUPPORT: "headset",
  SALES_ASSISTANT: "sparkles",
  CUSTOM: "bot",
};

export const toGlyph = (role: EmployeeRole): EmployeeGlyph => GLYPH_BY_ROLE[role];

// --- Sequence ------------------------------------------------------------

/**
 * `sequence` is the frontend's ordinal for recency. `created_at` is real
 * backend data, so the ordering it produces is the backend's, not invented —
 * an unparseable timestamp falls back to 0 rather than to "now".
 */
export function toSequence(createdAt: string): number {
  const parsed = Date.parse(createdAt);
  return Number.isNaN(parsed) ? 0 : parsed;
}

// --- Memory --------------------------------------------------------------

/**
 * Memory counts come from the Sprint 2E statistics endpoint. `latest` stays
 * `null`: the stats endpoint reports counts only, and fetching the newest
 * memory line would be a second request per profile for one string.
 */
export function toMemorySummary(stats: MemoryStatsResponse | null): EmployeeMemorySummary {
  if (!stats) return { total: 0, categories: [], latest: null };
  return {
    total: stats.total_memories,
    categories: [
      { category: "Permanent", count: stats.permanent_count },
      { category: "Working", count: stats.working_count },
      { category: "Learned", count: stats.learned_count },
    ].filter((entry) => entry.count > 0),
    latest: null,
  };
}

// --- Employee ------------------------------------------------------------

export function toEmployeeSummary(employee: EmployeeResponse): EmployeeSummary {
  const { role, customRole } = toRole(employee.role);

  return {
    id: employee.id,
    name: employee.name,
    role,
    customRole,
    description: employee.description ?? "",
    status: toStatus(employee.status),
    // Health, capabilities, assignment counts and activity have no backend
    // source yet. They report "nothing known" so the UI shows its empty states.
    health: "UNKNOWN",
    accent: toAccent(employee.id),
    glyph: toGlyph(role),
    capabilities: [],
    assignedWorkflows: 0,
    lastActivity: "",
    sequence: toSequence(employee.created_at),
  };
}

export function toEmployeeDetail(
  employee: EmployeeResponse,
  stats: MemoryStatsResponse | null,
): EmployeeDetail {
  return {
    ...toEmployeeSummary(employee),
    // `personality` is the closest stored equivalent of the builder's
    // behaviour note, and is what the create payload writes it to.
    behaviorSummary: employee.personality ?? "",
    configuration: { ...DEFAULT_CONFIGURATION, language: employee.language },
    // Permission levels and capability grants are not stored anywhere, so the
    // profile shows its empty state rather than a fabricated set of grants.
    permissions: [],
    assignments: { workflows: [], currentTask: null, queue: [] },
    memory: toMemorySummary(stats),
  };
}

/** The create payload, carrying only the fields the backend actually stores. */
export function toCreatePayload(draft: EmployeeDraft) {
  return {
    name: draft.name.trim(),
    role: fromRole(draft.role, draft.customRole),
    description: draft.description.trim() || null,
    language: draft.configuration.language || "en",
    personality: draft.behaviorSummary.trim() || null,
  };
}

