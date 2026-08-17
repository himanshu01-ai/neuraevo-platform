import { EMPLOYEE_PERMISSIONS, type EmployeePermissionId } from "@/services/employees";

/**
 * What each permission means, in the user's words. The levels and the
 * capability each one depends on belong to `services/employees`; only the
 * wording lives here.
 */

export interface PermissionMeta {
  id: EmployeePermissionId;
  label: string;
  description: string;
}

export const PERMISSION_META: Record<EmployeePermissionId, PermissionMeta> = {
  read_memory: {
    id: "read_memory",
    label: "Recall memories",
    description: "Look up what it already knows before answering.",
  },
  write_memory: {
    id: "write_memory",
    label: "Store memories",
    description: "Keep what it learns for next time.",
  },
  browse_web: {
    id: "browse_web",
    label: "Browse the web",
    description: "Open pages and read what's on them.",
  },
  run_code: {
    id: "run_code",
    label: "Run code",
    description: "Execute Python in a sandbox to work something out.",
  },
  modify_files: {
    id: "modify_files",
    label: "Modify files",
    description: "Write to documents, not just read them.",
  },
  send_email: {
    id: "send_email",
    label: "Send email",
    description: "Send a message that leaves your account.",
  },
  schedule_events: {
    id: "schedule_events",
    label: "Schedule events",
    description: "Put something on a calendar other people see.",
  },
  request_approval: {
    id: "request_approval",
    label: "Request approval",
    description: "Stop and ask you before going further.",
  },
};

/** Every permission in canonical order. */
export const PERMISSION_LIST: readonly PermissionMeta[] = EMPLOYEE_PERMISSIONS.map(
  (id) => PERMISSION_META[id]
);
