"use client";

import { useOnboardingStore, ONBOARDING_STEPS } from "@/store/auth";

/** Ergonomic view over the onboarding store for the wizard + steps. */
export function useOnboarding() {
  const stepIndex = useOnboardingStore((s) => s.stepIndex);
  const direction = useOnboardingStore((s) => s.direction);
  const data = useOnboardingStore((s) => s.data);
  const next = useOnboardingStore((s) => s.next);
  const prev = useOnboardingStore((s) => s.prev);
  const goTo = useOnboardingStore((s) => s.goTo);
  const updateData = useOnboardingStore((s) => s.updateData);
  const finish = useOnboardingStore((s) => s.finish);

  const total = ONBOARDING_STEPS.length;

  return {
    stepIndex,
    direction,
    data,
    next,
    prev,
    goTo,
    updateData,
    finish,
    steps: ONBOARDING_STEPS,
    total,
    isFirst: stepIndex === 0,
    isLast: stepIndex === total - 1,
    progress: (stepIndex / (total - 1)) * 100,
  };
}
