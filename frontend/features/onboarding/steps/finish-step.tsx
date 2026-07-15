"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";
import { useOnboarding } from "../hooks/use-onboarding";
import { StepShell } from "../components/step-shell";
import { WizardNav } from "../components/wizard-nav";

export function FinishStep() {
  const { data, prev, finish } = useOnboarding();
  const router = useRouter();
  const reduce = useReducedMotion();
  const [submitting, setSubmitting] = useState(false);

  const complete = () => {
    setSubmitting(true);
    finish();
    router.replace("/workspace");
  };

  const firstName = data.fullName?.split(" ")[0];
  const summary = [
    { label: "Name", value: data.fullName },
    { label: "Role", value: data.role },
    { label: "Company", value: data.companyName },
    { label: "Style", value: data.aiTone },
    { label: "Autonomy", value: data.aiAutonomy },
    {
      label: "Capabilities",
      value: data.aiCapabilities?.length ? `${data.aiCapabilities.length} enabled` : undefined,
    },
  ].filter((row): row is { label: string; value: string } => Boolean(row.value));

  return (
    <StepShell
      eyebrow="All set"
      title="Your AI employee is ready"
      description="Review your setup and enter your workspace."
    >
      <div className="flex flex-col items-center gap-4 rounded-lg border bg-card p-8 text-center shadow-sm">
        <motion.span
          initial={reduce ? undefined : { scale: 0.6, opacity: 0 }}
          animate={reduce ? undefined : { scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 360, damping: 20 }}
          className="inline-flex size-14 items-center justify-center rounded-full bg-success/15 text-success"
        >
          <Check className="size-7" strokeWidth={2.5} aria-hidden="true" />
        </motion.span>
        <p className="text-sm text-muted-foreground">
          Configuration complete{firstName ? `, ${firstName}` : ""}.
        </p>
      </div>

      {summary.length ? (
        <dl className="mt-6 divide-y overflow-hidden rounded-lg border bg-card text-sm">
          {summary.map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-4 px-4 py-2.5">
              <dt className="text-muted-foreground">{row.label}</dt>
              <dd className="min-w-0 truncate font-medium text-foreground">{row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      <div className="mt-8">
        <WizardNav
          onBack={prev}
          isSubmit={false}
          onNext={complete}
          nextLabel="Enter workspace"
          loading={submitting}
        />
      </div>
    </StepShell>
  );
}
