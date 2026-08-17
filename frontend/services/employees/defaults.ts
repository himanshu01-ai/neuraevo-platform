import type { EmployeeConfiguration } from "./types";

/**
 * The configuration an employee starts with when nothing else is known.
 *
 * One declaration for the whole app: the builder store seeds a new draft from
 * it, the fixtures build on it, and the backend mapping falls back to it for
 * the settings the backend does not yet store. Deliberately conservative —
 * approval is required until someone says otherwise.
 */
export const DEFAULT_CONFIGURATION: EmployeeConfiguration = {
  autonomy: "balanced",
  tone: "professional",
  executionMode: "SEQUENTIAL",
  priority: "MEDIUM",
  requireApproval: true,
  language: "en",
};

