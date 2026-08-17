import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Onboarding wizard state. Persisted to localStorage so progress and the
 * in-progress AI-employee configuration survive reloads (progress preservation).
 * Holds temporary profile data only — no business logic, no backend writes.
 */

export const ONBOARDING_STEPS = [
  { id: "welcome", label: "Welcome" },
  { id: "profile", label: "Profile" },
  { id: "company", label: "Company" },
  { id: "ai", label: "AI preferences" },
  { id: "workspace", label: "Workspace" },
  { id: "finish", label: "Finish" },
] as const;

export type OnboardingStepId = (typeof ONBOARDING_STEPS)[number]["id"];

export interface OnboardingData {
  fullName?: string;
  role?: string;
  companyName?: string;
  companySize?: string;
  industry?: string;
  aiTone?: string;
  aiAutonomy?: string;
  aiCapabilities?: string[];
  density?: string;
  notifications?: string[];
}

interface OnboardingState {
  stepIndex: number;
  /** Navigation direction, for step transition animation. */
  direction: 1 | -1;
  finished: boolean;
  data: OnboardingData;
  next: () => void;
  prev: () => void;
  goTo: (index: number) => void;
  updateData: (partial: Partial<OnboardingData>) => void;
  finish: () => void;
  reset: () => void;
}

const LAST_INDEX = ONBOARDING_STEPS.length - 1;

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      stepIndex: 0,
      direction: 1,
      finished: false,
      data: {},
      next: () => set((s) => ({ stepIndex: Math.min(LAST_INDEX, s.stepIndex + 1), direction: 1 })),
      prev: () => set((s) => ({ stepIndex: Math.max(0, s.stepIndex - 1), direction: -1 })),
      goTo: (index) =>
        set((s) => ({
          stepIndex: Math.max(0, Math.min(LAST_INDEX, index)),
          direction: index >= s.stepIndex ? 1 : -1,
        })),
      updateData: (partial) => set((s) => ({ data: { ...s.data, ...partial } })),
      finish: () => set({ finished: true }),
      reset: () => set({ stepIndex: 0, direction: 1, finished: false, data: {} }),
    }),
    { name: "neuraevo.onboarding" }
  )
);
