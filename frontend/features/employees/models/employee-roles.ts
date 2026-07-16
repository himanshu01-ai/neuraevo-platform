import {
  Bot,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  Code,
  Headset,
  PenLine,
  Search,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { EMPLOYEE_ROLES, type EmployeeRole } from "@/services/employees";

/**
 * What each role is and how it looks. Presentation only — the vocabulary itself
 * belongs to `services/employees`, which is why nothing here is re-declared.
 *
 * Role chips are deliberately neutral. Colour in this system carries status, so
 * tinting a role would spend a semantic signal on a non-semantic distinction;
 * the icon carries the category instead.
 */

export interface RoleMeta {
  role: EmployeeRole;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const ROLE_META: Record<EmployeeRole, RoleMeta> = {
  RESEARCH_ASSISTANT: {
    role: "RESEARCH_ASSISTANT",
    label: "Research Assistant",
    description: "Finds what's known and reports back.",
    icon: Search,
  },
  SOFTWARE_ENGINEER: {
    role: "SOFTWARE_ENGINEER",
    label: "Software Engineer",
    description: "Reads code, writes changes, opens reviews.",
    icon: Code,
  },
  DATA_ANALYST: {
    role: "DATA_ANALYST",
    label: "Data Analyst",
    description: "Turns raw numbers into an answer.",
    icon: ChartNoAxesCombined,
  },
  PROJECT_MANAGER: {
    role: "PROJECT_MANAGER",
    label: "Project Manager",
    description: "Keeps the plan and the people in sync.",
    icon: BriefcaseBusiness,
  },
  CONTENT_WRITER: {
    role: "CONTENT_WRITER",
    label: "Content Writer",
    description: "Drafts in your voice.",
    icon: PenLine,
  },
  CUSTOMER_SUPPORT: {
    role: "CUSTOMER_SUPPORT",
    label: "Customer Support",
    description: "Answers customers and escalates the rest.",
    icon: Headset,
  },
  SALES_ASSISTANT: {
    role: "SALES_ASSISTANT",
    label: "Sales Assistant",
    description: "Preps the call and follows up after it.",
    icon: TrendingUp,
  },
  CUSTOM: {
    role: "CUSTOM",
    label: "Custom",
    description: "Define the job yourself.",
    icon: Bot,
  },
};

/** Every role in canonical order. */
export const ROLE_LIST: readonly RoleMeta[] = EMPLOYEE_ROLES.map((role) => ROLE_META[role]);

/**
 * The role as it should read on screen. A `CUSTOM` role shows the title the user
 * typed; every other role shows its own label. The one place this choice is
 * made, so a card and a profile can't disagree.
 */
export function roleLabel(role: EmployeeRole, customRole: string): string {
  if (role === "CUSTOM") return customRole.trim() || ROLE_META.CUSTOM.label;
  return ROLE_META[role].label;
}
