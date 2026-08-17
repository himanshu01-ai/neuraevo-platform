"use client";

import { AnimatedMark } from "@/components/brand/animated-mark";
import { StepShell } from "../components/step-shell";
import { WizardNav } from "../components/wizard-nav";
import { useOnboarding } from "../hooks/use-onboarding";

export function WelcomeStep() {
  const { next } = useOnboarding();
  return (
    <StepShell
      eyebrow="Welcome"
      title="Let's set up your AI employee"
      description="A few quick questions so NeuraEvo can plan, execute, and report exactly the way you want."
    >
      <div className="flex items-center gap-4 rounded-lg border bg-card p-6 shadow-sm">
        <AnimatedMark className="size-14 shrink-0" />
        <p className="text-sm text-muted-foreground">
          This takes about two minutes. Your progress is saved automatically as you go.
        </p>
      </div>
      <WizardNav showBack={false} isSubmit={false} onNext={next} nextLabel="Get started" />
    </StepShell>
  );
}
