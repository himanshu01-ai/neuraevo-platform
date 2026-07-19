/**
 * Employee domain contracts — provider-independent. The employees feature
 * depends only on these types and the `EmployeesAdapter` interface, never on a
 * concrete provider. Sprint 17.6 ships a deterministic mock adapter; a real
 * backend adapter can be dropped in later with zero changes to callers.
 *
 * Where a vocabulary mirrors the frozen backend it is imported from
 * `types/domain.ts` and never redefined here. Three vocabularies below have no
 * backend counterpart and so are deliberately owned by this layer rather than
 * `types/domain.ts` (which mirrors backend contracts only) — the same call
 * `services/workflows/types.ts` makes for `NODE_KINDS`. Each says why in place.
 *
 * Nothing in this layer executes anything. It describes an employee; the
 * platform is what runs one.
 */

import { CAPABILITIES, type Capability, type ExecutionMode, type HealthState, type LifecycleStatus, type Priority, type StatusTone } from "@/types/domain";

/**
 * Deterministic ordinal standing in for recency, mirroring the backend's
 * `generated_sequence`. Higher is more recent. No clock times.
 */
export type Sequence = number;

// =====================================================================
// Status
// =====================================================================

/**
 * How an employee presents right now.
 *
 * This is a frontend vocabulary. The backend's `Employee.status` is a
 * free-form `String(50)` defaulting to `"draft"` and its `EmployeeSessionStatus`
 * describes a *session*, not the employee — so there is no contract to mirror
 * and this does not belong in `types/domain.ts`. Sprint 17.7 maps whatever the
 * backend reports onto these labels; the mapping is the integration's job.
 */
export const EMPLOYEE_STATUS = [
  "AVAILABLE",
  "BUSY",
  "WORKING",
  "PAUSED",
  "OFFLINE",
  "UNKNOWN",
] as const;
export type EmployeeStatus = (typeof EMPLOYEE_STATUS)[number];

/**
 * Status → tone. Colour still resolves through the one `StatusTone` scale in
 * `types/domain.ts`, so an employee's status renders in the same five colours as
 * every other status in the app. BUSY and PAUSED share a tone the way PENDING
 * and CANCELLED do in `LIFECYCLE_TONE` — the label carries the distinction.
 */
export const EMPLOYEE_STATUS_TONE: Record<EmployeeStatus, StatusTone> = {
  AVAILABLE: "success",
  BUSY: "warning",
  WORKING: "info",
  PAUSED: "warning",
  OFFLINE: "neutral",
  UNKNOWN: "neutral",
};

export const EMPLOYEE_STATUS_LABEL: Record<EmployeeStatus, string> = {
  AVAILABLE: "Available",
  BUSY: "Busy",
  WORKING: "Working",
  PAUSED: "Paused",
  OFFLINE: "Offline",
  UNKNOWN: "Unknown",
};

// =====================================================================
// Roles
// =====================================================================

/**
 * The roles an employee can be hired into. `CUSTOM` carries a free-text title in
 * `customRole`, which is what the backend's free-form `Employee.role`
 * (`String(255)`) already accepts — so this list is a frontend authoring
 * vocabulary, not a backend enum.
 */
export const EMPLOYEE_ROLES = [
  "RESEARCH_ASSISTANT",
  "SOFTWARE_ENGINEER",
  "DATA_ANALYST",
  "PROJECT_MANAGER",
  "CONTENT_WRITER",
  "CUSTOMER_SUPPORT",
  "SALES_ASSISTANT",
  "CUSTOM",
] as const;
export type EmployeeRole = (typeof EMPLOYEE_ROLES)[number];

// =====================================================================
// Capabilities
// =====================================================================

/**
 * Platform subsystems an employee can be granted, beyond the six executable
 * capabilities. `services/workflows/types.ts` draws the same line: memory,
 * approval and notification are subsystems, not capabilities, which is why
 * `Capability` in `types/domain.ts` stays at six and is not widened here.
 */
export const PLATFORM_GRANTS = ["memory", "approval", "notification"] as const;
export type PlatformGrant = (typeof PLATFORM_GRANTS)[number];

/** Everything an employee can hold: the six capabilities plus the three grants. */
export const EMPLOYEE_CAPABILITIES = [...CAPABILITIES, ...PLATFORM_GRANTS] as const;
export type EmployeeCapability = (typeof EMPLOYEE_CAPABILITIES)[number];

/** Narrows an employee capability to one of the backend's executable six. */
export const isCapability = (value: EmployeeCapability): value is Capability =>
  (CAPABILITIES as readonly string[]).includes(value);

/** Whether this employee holds the capability. */
export const CAPABILITY_GRANT_STATUS = ["GRANTED", "NOT_GRANTED"] as const;
export type CapabilityGrantStatus = (typeof CAPABILITY_GRANT_STATUS)[number];

/** Whether the platform can run the capability yet — independent of any grant. */
export const CAPABILITY_AVAILABILITY = ["GENERAL", "PREVIEW", "COMING_SOON"] as const;
export type CapabilityAvailability = (typeof CAPABILITY_AVAILABILITY)[number];

/** One capability as it stands for one employee: granted?, and offered by the platform? */
export interface EmployeeCapabilityState {
  capability: EmployeeCapability;
  status: CapabilityGrantStatus;
  availability: CapabilityAvailability;
}

// =====================================================================
// Appearance
// =====================================================================

/**
 * An employee's accent. These are names for tones the theme already ships, not
 * new colours — `features/employees/models/employee-appearance.ts` resolves each
 * to existing token classes. Confined to the avatar, never to status.
 */
export const EMPLOYEE_ACCENTS = ["violet", "blue", "emerald", "amber", "rose", "slate"] as const;
export type EmployeeAccent = (typeof EMPLOYEE_ACCENTS)[number];

/** The glyph shown on the avatar. `initials` falls back to the shared <Avatar>. */
export const EMPLOYEE_GLYPHS = [
  "initials",
  "bot",
  "brain",
  "code",
  "chart",
  "pen",
  "headset",
  "briefcase",
  "sparkles",
] as const;
export type EmployeeGlyph = (typeof EMPLOYEE_GLYPHS)[number];

// =====================================================================
// Configuration
// =====================================================================

/**
 * How the employee should behave when the platform runs it. The values match the
 * onboarding vocabulary (`features/onboarding/steps/options.ts`) so a user meets
 * one set of words; they are restated rather than imported because features
 * never import across each other.
 */
export const AUTONOMY_LEVELS = ["ask", "balanced", "autonomous"] as const;
export type AutonomyLevel = (typeof AUTONOMY_LEVELS)[number];

export const EMPLOYEE_TONES = ["professional", "friendly", "concise"] as const;
export type EmployeeTone = (typeof EMPLOYEE_TONES)[number];

export interface EmployeeConfiguration {
  autonomy: AutonomyLevel;
  tone: EmployeeTone;
  /** Default ordering the platform would use for this employee's work. */
  executionMode: ExecutionMode;
  priority: Priority;
  /** Whether a run would pause for approval. Structure only. */
  requireApproval: boolean;
  /** Mirrors the backend's `Employee.language` (defaults to "en"). */
  language: string;
}

// =====================================================================
// Permissions
// =====================================================================

export const EMPLOYEE_PERMISSIONS = [
  "read_memory",
  "write_memory",
  "browse_web",
  "run_code",
  "modify_files",
  "send_email",
  "schedule_events",
  "request_approval",
] as const;
export type EmployeePermissionId = (typeof EMPLOYEE_PERMISSIONS)[number];

export const PERMISSION_LEVELS = ["ALLOWED", "ASK_FIRST", "BLOCKED"] as const;
export type PermissionLevel = (typeof PERMISSION_LEVELS)[number];

export const PERMISSION_TONE: Record<PermissionLevel, StatusTone> = {
  ALLOWED: "success",
  ASK_FIRST: "warning",
  BLOCKED: "neutral",
};

export const PERMISSION_LEVEL_LABEL: Record<PermissionLevel, string> = {
  ALLOWED: "Allowed",
  ASK_FIRST: "Ask first",
  BLOCKED: "Blocked",
};

export interface EmployeePermission {
  id: EmployeePermissionId;
  level: PermissionLevel;
}

/**
 * The capability each permission depends on. A permission is meaningless without
 * its capability, so this table is the one place that pairing is stated — the
 * fixtures seed from it and the adapter reconciles against it.
 */
export const PERMISSION_REQUIRES: Record<EmployeePermissionId, EmployeeCapability> = {
  read_memory: "memory",
  write_memory: "memory",
  browse_web: "browser",
  run_code: "python",
  modify_files: "files",
  send_email: "email",
  schedule_events: "calendar",
  request_approval: "approval",
};

/**
 * Where a permission lands when its capability is granted. Reading is allowed;
 * anything that leaves a mark outside the platform asks first. Deliberately
 * conservative — the user can loosen it, but nothing loosens itself.
 */
export const PERMISSION_DEFAULT_LEVEL: Record<EmployeePermissionId, PermissionLevel> = {
  read_memory: "ALLOWED",
  write_memory: "ASK_FIRST",
  browse_web: "ALLOWED",
  run_code: "ASK_FIRST",
  modify_files: "ASK_FIRST",
  send_email: "ASK_FIRST",
  schedule_events: "ASK_FIRST",
  request_approval: "ALLOWED",
};

// =====================================================================
// Assignments
// =====================================================================

/** A workflow this employee is assigned to. Assignment is not execution. */
export interface EmployeeAssignment {
  workflowId: string;
  workflowName: string;
  priority: Priority;
  executionMode: ExecutionMode;
  /** Plain-language note on what this workflow waits for. Never computed here. */
  dependencySummary: string;
}

/** What the platform reports the employee is on right now. Read-only. */
export interface EmployeeCurrentTask {
  id: string;
  title: string;
  workflowName: string;
  status: LifecycleStatus;
  /** 0–100, carried from the platform — never derived by the UI. */
  progress: number;
}

export interface EmployeeQueueItem {
  id: string;
  title: string;
  priority: Priority;
  /** 1-based place in line, as the platform ordered it. */
  position: number;
}

export interface EmployeeAssignments {
  workflows: EmployeeAssignment[];
  /** `null` when the employee isn't on anything. */
  currentTask: EmployeeCurrentTask | null;
  queue: EmployeeQueueItem[];
}

// =====================================================================
// Activity
// =====================================================================

export const ACTIVITY_KINDS = [
  "CREATED",
  "UPDATED",
  "ASSIGNED",
  "PAUSED",
  "RESUMED",
  "COMPLETED",
  "CONFIGURATION_CHANGED",
] as const;
export type ActivityKind = (typeof ACTIVITY_KINDS)[number];

export interface EmployeeActivityEvent {
  id: string;
  kind: ActivityKind;
  /** One line naming what happened. Fixture copy — nothing is inferred. */
  summary: string;
  sequence: Sequence;
}

// =====================================================================
// Memory
// =====================================================================

/** Counts the Memory Engine already reports (Sprint 2E). Never recomputed here. */
export interface EmployeeMemorySummary {
  total: number;
  categories: { category: string; count: number }[];
  /** The most recently stored line, or `null` when nothing is stored. */
  latest: string | null;
}

// =====================================================================
// Employee
// =====================================================================

/** What the directory list and cards need. */
export interface EmployeeSummary {
  id: string;
  name: string;
  role: EmployeeRole;
  /** Set only when `role` is `CUSTOM`; the free-text title the user typed. */
  customRole: string;
  description: string;
  status: EmployeeStatus;
  health: HealthState;
  accent: EmployeeAccent;
  glyph: EmployeeGlyph;
  capabilities: EmployeeCapability[];
  /** How many workflows are assigned. The list never counts this itself. */
  assignedWorkflows: number;
  /** One line on the latest activity, for the card's activity slot. */
  lastActivity: string;
  sequence: Sequence;
}

/** Everything a profile shows. */
export interface EmployeeDetail extends EmployeeSummary {
  /** How the employee describes its own way of working. */
  behaviorSummary: string;
  configuration: EmployeeConfiguration;
  permissions: EmployeePermission[];
  assignments: EmployeeAssignments;
  memory: EmployeeMemorySummary;
}

/** What the builder hands back when saving. */
export interface EmployeeDraft {
  /** `null` for a create; an id for an edit. */
  id: string | null;
  name: string;
  role: EmployeeRole;
  customRole: string;
  description: string;
  behaviorSummary: string;
  accent: EmployeeAccent;
  glyph: EmployeeGlyph;
  capabilities: EmployeeCapability[];
  configuration: EmployeeConfiguration;
}

// =====================================================================
// Templates
// =====================================================================

export interface EmployeeTemplateSummary {
  id: string;
  name: string;
  description: string;
  category: string;
  role: EmployeeRole;
  accent: EmployeeAccent;
  glyph: EmployeeGlyph;
  capabilities: EmployeeCapability[];
}

/** A template is a pre-filled draft: everything the builder needs to start. */
export interface EmployeeTemplate extends EmployeeTemplateSummary {
  behaviorSummary: string;
  configuration: EmployeeConfiguration;
}

// =====================================================================
// Errors & the adapter seam
// =====================================================================

export type EmployeeErrorCode =
  | "not_found"
  | "unavailable"
  | "invalid_draft"
  | "unknown";

export class EmployeeError extends Error {
  code: EmployeeErrorCode;
  constructor(code: EmployeeErrorCode, message: string) {
    super(message);
    this.name = "EmployeeError";
    this.code = code;
  }
}

/** The single seam every employee backend must implement. */
export interface EmployeesAdapter {
  list(): Promise<EmployeeSummary[]>;
  detail(id: string): Promise<EmployeeDetail>;
  save(draft: EmployeeDraft): Promise<EmployeeDetail>;
  duplicate(id: string): Promise<EmployeeDetail>;
  archive(id: string): Promise<EmployeeDetail>;
  remove(id: string): Promise<void>;
  activity(id: string): Promise<EmployeeActivityEvent[]>;
  capabilities(id: string): Promise<EmployeeCapabilityState[]>;
  templates(): Promise<EmployeeTemplateSummary[]>;
  template(id: string): Promise<EmployeeTemplate>;
}
