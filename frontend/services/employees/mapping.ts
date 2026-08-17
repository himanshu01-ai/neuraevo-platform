import { z } from "zod";
import { DEFAULT_CONFIGURATION } from "./defaults";
import {
  EMPLOYEE_ROLES,
  PERMISSION_DEFAULT_LEVEL,
  PERMISSION_REQUIRES,
  type ActivityKind,
  type EmployeeAccent,
  type EmployeeActivityEvent,
  type EmployeeAssignment,
  type EmployeeCapability,
  type EmployeeDetail,
  type EmployeeDraft,
  type EmployeeGlyph,
  type EmployeeMemorySummary,
  type EmployeePermission,
  type EmployeeRole,
  type EmployeeStatus,
  type EmployeeSummary,
  type PermissionLevel,
} from "./types";
import type { ExecutionMode, HealthState, Priority } from "@/types/domain";

/**
 * Translation between the backend's employee contracts and this layer's
 * presentation models. The two never meet anywhere else: the adapter speaks
 * HTTP, the feature speaks `EmployeeSummary`/`EmployeeDetail`, and everything
 * in between happens here.
 *
 * Sprint 18.2A completed the backend, so almost everything is now a real
 * mapping of stored data — configuration, capabilities, permissions,
 * appearance, health and assignments all come from the database. The two
 * vocabularies differ in casing and in a few names, which is what the tables
 * below reconcile.
 */

// --- Backend wire schemas ------------------------------------------------
// Mirrors of backend/app/schemas/employee.py and memory_stats.py.

const permissionResponseSchema = z.object({
  permission: z.string(),
  level: z.string(),
});

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
  updated_at: z.string().nullable().optional(),
  autonomy: z.string(),
  tone: z.string(),
  execution_mode: z.string(),
  priority: z.string(),
  require_approval: z.boolean(),
  accent: z.string(),
  glyph: z.string(),
  archived_at: z.string().nullable().optional(),
  health: z.string(),
  // Optional rather than defaulted: an older backend that predates these
  // fields still parses, and the mappers below supply the empty value.
  capabilities: z.array(z.string()).optional(),
  permissions: z.array(permissionResponseSchema).optional(),
  assignment_count: z.number().optional(),
});

export type EmployeeResponse = z.infer<typeof employeeResponseSchema>;

export const activityResponseSchema = z.object({
  id: z.string(),
  kind: z.string(),
  summary: z.string(),
  sequence: z.number(),
  created_at: z.string(),
});

export const assignmentResponseSchema = z.object({
  id: z.string(),
  workflow_id: z.string(),
  workflow_name: z.string(),
  priority: z.string(),
  execution_mode: z.string(),
  dependency_summary: z.string().nullable().optional(),
  created_at: z.string(),
});

export type AssignmentResponse = z.infer<typeof assignmentResponseSchema>;

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
 * The backend describes an employee's *lifecycle*; this layer describes how it
 * *presents*. They are close but not identical, so the mapping is explicit:
 *
 *   draft    -> UNKNOWN    nothing has observed it yet
 *   ready    -> AVAILABLE  described and on the bench
 *   active   -> WORKING    in service
 *   paused   -> PAUSED
 *   archived -> OFFLINE    retired but restorable
 *   error    -> OFFLINE    not usable; `health` carries the severity
 */
const STATUS_BY_BACKEND_VALUE: Record<string, EmployeeStatus> = {
  draft: "UNKNOWN",
  ready: "AVAILABLE",
  active: "WORKING",
  paused: "PAUSED",
  archived: "OFFLINE",
  error: "OFFLINE",
};

export function toStatus(status: string): EmployeeStatus {
  return STATUS_BY_BACKEND_VALUE[status.trim().toLowerCase()] ?? "UNKNOWN";
}

/**
 * Whether the backend considers this employee archived.
 *
 * Read from the lifecycle value rather than the mapped status, because
 * `archived` and `error` both present as `OFFLINE` — and restoring is only
 * legal from the first. This is the same condition the backend guards its
 * restore endpoint with, so the UI and the server agree on who can be restored.
 */
export function toIsArchived(status: string): boolean {
  return status.trim().toLowerCase() === "archived";
}

const HEALTH_BY_BACKEND_VALUE: Record<string, HealthState> = {
  healthy: "HEALTHY",
  degraded: "DEGRADED",
  unhealthy: "UNHEALTHY",
  unknown: "UNKNOWN",
};

export function toHealth(health: string): HealthState {
  return HEALTH_BY_BACKEND_VALUE[health.trim().toLowerCase()] ?? "UNKNOWN";
}

// --- Configuration -------------------------------------------------------
//
// The two sides use the same words in different casing. These tables are the
// one place that is reconciled, in both directions.

const upper = <T extends string>(value: string, fallback: T): T =>
  (value ? (value.toUpperCase() as T) : fallback);

export function toConfiguration(employee: EmployeeResponse) {
  return {
    autonomy: (employee.autonomy ||
      DEFAULT_CONFIGURATION.autonomy) as EmployeeDetail["configuration"]["autonomy"],
    tone: (employee.tone ||
      DEFAULT_CONFIGURATION.tone) as EmployeeDetail["configuration"]["tone"],
    executionMode: upper<ExecutionMode>(
      employee.execution_mode,
      DEFAULT_CONFIGURATION.executionMode,
    ),
    priority: upper<Priority>(employee.priority, DEFAULT_CONFIGURATION.priority),
    requireApproval: employee.require_approval,
    language: employee.language,
  };
}

export function toPermissions(
  permissions: { permission: string; level: string }[],
): EmployeePermission[] {
  return permissions.map((entry) => ({
    id: entry.permission as EmployeePermission["id"],
    level: entry.level.toUpperCase() as PermissionLevel,
  }));
}

// --- Appearance ----------------------------------------------------------
// Stored by the backend since Sprint 18.2A, so these are plain reads.

export const toAccent = (accent: string): EmployeeAccent =>
  (accent || "slate") as EmployeeAccent;

export const toGlyph = (glyph: string): EmployeeGlyph =>
  (glyph || "bot") as EmployeeGlyph;

// --- Sequence ------------------------------------------------------------

/**
 * `sequence` is the frontend's ordinal for recency, taken from real backend
 * timestamps — an unparseable value falls back to 0 rather than to "now".
 */
export function toSequence(createdAt: string): number {
  const parsed = Date.parse(createdAt);
  return Number.isNaN(parsed) ? 0 : parsed;
}

// --- Activity ------------------------------------------------------------

/**
 * The backend records more kinds than this layer draws icons for, so several
 * collapse onto the nearest frontend kind. The event's own summary text
 * carries the detail either way.
 */
const ACTIVITY_KIND_BY_BACKEND_VALUE: Record<string, ActivityKind> = {
  created: "CREATED",
  updated: "UPDATED",
  configuration_changed: "CONFIGURATION_CHANGED",
  status_changed: "UPDATED",
  archived: "PAUSED",
  restored: "RESUMED",
  assigned: "ASSIGNED",
  unassigned: "UPDATED",
};

export function toActivityEvent(event: {
  id: string;
  kind: string;
  summary: string;
  sequence: number;
}): EmployeeActivityEvent {
  return {
    id: event.id,
    kind: ACTIVITY_KIND_BY_BACKEND_VALUE[event.kind] ?? "UPDATED",
    summary: event.summary,
    sequence: event.sequence,
  };
}

// --- Assignments ---------------------------------------------------------

export function toAssignment(assignment: AssignmentResponse): EmployeeAssignment {
  return {
    workflowId: assignment.workflow_id,
    workflowName: assignment.workflow_name,
    priority: upper<Priority>(assignment.priority, "MEDIUM"),
    executionMode: upper<ExecutionMode>(assignment.execution_mode, "SEQUENTIAL"),
    dependencySummary: assignment.dependency_summary ?? "",
  };
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
    isArchived: toIsArchived(employee.status),
    health: toHealth(employee.health),
    accent: toAccent(employee.accent),
    glyph: toGlyph(employee.glyph),
    capabilities: (employee.capabilities ?? []) as EmployeeCapability[],
    assignedWorkflows: employee.assignment_count ?? 0,
    // The employee endpoints don't carry a latest-activity line, and asking
    // for one per row would be a request per card. The profile's timeline is
    // where history is read.
    lastActivity: "",
    sequence: toSequence(employee.created_at),
  };
}

export function toEmployeeDetail(
  employee: EmployeeResponse,
  stats: MemoryStatsResponse | null,
  assignments: AssignmentResponse[] = [],
): EmployeeDetail {
  return {
    ...toEmployeeSummary(employee),
    // `personality` is the stored home of the builder's behaviour note.
    behaviorSummary: employee.personality ?? "",
    configuration: toConfiguration(employee),
    permissions: toPermissions(employee.permissions ?? []),
    assignments: {
      workflows: assignments.map(toAssignment),
      // A current task and a queue describe *execution*, which this domain
      // deliberately does not model. They stay empty until it does.
      currentTask: null,
      queue: [],
    },
    memory: toMemorySummary(stats),
  };
}

// --- Draft -> backend ----------------------------------------------------

/** Everything both writes share. The backend takes the same shape for each. */
function toWritePayload(draft: EmployeeDraft) {
  return {
    name: draft.name.trim(),
    role: fromRole(draft.role, draft.customRole),
    description: draft.description.trim() || null,
    language: draft.configuration.language || "en",
    personality: draft.behaviorSummary.trim() || null,
    autonomy: draft.configuration.autonomy,
    tone: draft.configuration.tone,
    execution_mode: draft.configuration.executionMode.toLowerCase(),
    priority: draft.configuration.priority.toLowerCase(),
    require_approval: draft.configuration.requireApproval,
    accent: draft.accent,
    glyph: draft.glyph,
    capabilities: draft.capabilities,
  };
}

/**
 * Create also seeds the permissions implied by the granted capabilities, using
 * the same `PERMISSION_DEFAULT_LEVEL` table the rest of the app reads — the
 * conservative default, never widened on the user's behalf.
 */
export function toCreatePayload(draft: EmployeeDraft) {
  const held = new Set(draft.capabilities);

  return {
    ...toWritePayload(draft),
    permissions: Object.entries(PERMISSION_REQUIRES)
      .filter(([, capability]) => held.has(capability))
      .map(([permission]) => ({
        permission,
        level: PERMISSION_DEFAULT_LEVEL[
          permission as keyof typeof PERMISSION_DEFAULT_LEVEL
        ].toLowerCase(),
      })),
  };
}

/**
 * Update deliberately sends no permissions.
 *
 * The builder has no permission controls, so sending a set would overwrite
 * levels chosen elsewhere with defaults. The backend reconciles permissions
 * against the new capabilities on its own, so revoking a capability still
 * blocks whatever depended on it.
 */
export const toUpdatePayload = toWritePayload;

