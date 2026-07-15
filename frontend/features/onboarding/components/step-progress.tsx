"use client";

import { Progress } from "@/components/ui/progress";
import { useOnboarding } from "../hooks/use-onboarding";
import { cn } from "@/lib/utils";

/** Progress bar + step labels for the onboarding wizard. */
export function StepProgress() {
  const { stepIndex, total, steps, progress } = useOnboarding();
  const current = steps[stepIndex];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground">{current?.label}</span>
        <span className="text-muted-foreground">
          Step {stepIndex + 1} of {total}
        </span>
      </div>
      <Progress value={progress} label="Onboarding progress" />
      <ol className="hidden justify-between gap-2 sm:flex" aria-hidden="true">
        {steps.map((s, i) => (
          <li key={s.id} className="flex items-center gap-1.5">
            <span className={cn("size-1.5 rounded-full transition-colors", i <= stepIndex ? "bg-primary" : "bg-muted")} />
            <span className={cn("text-xs", i === stepIndex ? "font-medium text-foreground" : "text-muted-foreground")}>
              {s.label}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
