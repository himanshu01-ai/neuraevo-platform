"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/layouts/theme-toggle";
import { useOnboarding } from "../hooks/use-onboarding";
import { StepProgress } from "./step-progress";
import {
  WelcomeStep,
  ProfileStep,
  CompanyStep,
  AiPreferencesStep,
  WorkspacePreferencesStep,
  FinishStep,
} from "../steps";

const STEP_COMPONENTS = [
  WelcomeStep,
  ProfileStep,
  CompanyStep,
  AiPreferencesStep,
  WorkspacePreferencesStep,
  FinishStep,
] as const;

/** The full-screen onboarding flow: brand chrome + progress + animated steps. */
export function OnboardingWizard() {
  const { stepIndex, direction } = useOnboarding();
  const reduce = useReducedMotion();
  const StepComponent = STEP_COMPONENTS[stepIndex] ?? WelcomeStep;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between p-4 sm:p-6">
        <Logo variant="wordmark" href="/" />
        <ThemeToggle />
      </header>

      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col px-4 py-6 sm:py-10">
        <StepProgress />
        <div className="relative mt-10 overflow-hidden">
          {/* Keyed remount animates each step in. No AnimatePresence exit — the
              steps' infinite child animations can stall `mode="wait"`. */}
          <motion.div
            key={stepIndex}
            initial={reduce ? { opacity: 0 } : { opacity: 0, x: direction * 28 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            <StepComponent />
          </motion.div>
        </div>
      </main>
    </div>
  );
}
