import { MessageSquare, Rocket, Scale, ShieldQuestion, Sparkles, Zap, type LucideIcon } from "lucide-react";
import { AUTONOMY_LEVELS, EMPLOYEE_TONES, type AutonomyLevel, type EmployeeTone } from "@/services/employees";

/**
 * How the configuration choices read on screen. The wording matches onboarding
 * (`features/onboarding/steps/options.ts`) so a user meets one set of words for
 * one idea; it is restated rather than imported because features never import
 * across each other.
 */

export interface ChoiceMeta<T extends string> {
  value: T;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const AUTONOMY_META: Record<AutonomyLevel, ChoiceMeta<AutonomyLevel>> = {
  ask: {
    value: "ask",
    label: "Ask first",
    description: "Check with me before acting.",
    icon: ShieldQuestion,
  },
  balanced: {
    value: "balanced",
    label: "Balanced",
    description: "Act, but pause on anything risky.",
    icon: Scale,
  },
  autonomous: {
    value: "autonomous",
    label: "Autonomous",
    description: "Run end-to-end; approvals only when required.",
    icon: Rocket,
  },
};

export const AUTONOMY_LIST: readonly ChoiceMeta<AutonomyLevel>[] = AUTONOMY_LEVELS.map(
  (value) => AUTONOMY_META[value]
);

export const TONE_META: Record<EmployeeTone, ChoiceMeta<EmployeeTone>> = {
  professional: {
    value: "professional",
    label: "Professional",
    description: "Precise, formal, to the point.",
    icon: Sparkles,
  },
  friendly: {
    value: "friendly",
    label: "Friendly",
    description: "Warm and conversational.",
    icon: MessageSquare,
  },
  concise: {
    value: "concise",
    label: "Concise",
    description: "Minimal words, maximum signal.",
    icon: Zap,
  },
};

export const TONE_LIST: readonly ChoiceMeta<EmployeeTone>[] = EMPLOYEE_TONES.map((value) => TONE_META[value]);
