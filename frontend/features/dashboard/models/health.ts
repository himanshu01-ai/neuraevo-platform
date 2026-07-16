import type { HealthSubsystem } from "@/services/dashboard";

/**
 * Operator-facing name for each backend subsystem. The keys are the backend's
 * own module names; only the casing changes for display.
 */
export const HEALTH_SUBSYSTEM_LABEL: Record<HealthSubsystem, string> = {
  planning: "Planning",
  runtime: "Runtime",
  memory: "Memory",
  scheduler: "Scheduler",
  recovery: "Recovery",
  persistence: "Persistence",
  operations: "Operations",
  validation: "Validation",
};
