"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { aiPreferencesSchema, type AiPreferencesValues } from "../validation/schemas";
import { TONES, AUTONOMY, CAPABILITIES } from "./options";
import { useOnboarding } from "../hooks/use-onboarding";
import { StepShell } from "../components/step-shell";
import { WizardNav } from "../components/wizard-nav";
import { OptionCard } from "@/components/ui/option-card";

function GroupError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-2 text-xs font-medium text-destructive">
      {message}
    </p>
  );
}

export function AiPreferencesStep() {
  const { data, updateData, next, prev } = useOnboarding();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AiPreferencesValues>({
    resolver: zodResolver(aiPreferencesSchema),
    defaultValues: {
      aiTone: data.aiTone ?? "",
      aiAutonomy: data.aiAutonomy ?? "",
      aiCapabilities: data.aiCapabilities ?? [],
    },
  });

  const onSubmit = handleSubmit((values) => {
    updateData(values);
    next();
  });

  return (
    <form onSubmit={onSubmit} noValidate>
      <StepShell
        eyebrow="AI preferences"
        title="Shape how it works"
        description="Set the personality and boundaries for your AI employee."
      >
        <div className="space-y-8">
          <fieldset>
            <legend className="mb-3 text-sm font-medium text-foreground">Communication style</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              {TONES.map((t) => (
                <OptionCard
                  key={t.value}
                  title={t.title}
                  description={t.description}
                  icon={t.icon}
                  inputProps={{ type: "radio", value: t.value, ...register("aiTone") }}
                />
              ))}
            </div>
            <GroupError message={errors.aiTone?.message} />
          </fieldset>

          <fieldset>
            <legend className="mb-3 text-sm font-medium text-foreground">Autonomy level</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              {AUTONOMY.map((a) => (
                <OptionCard
                  key={a.value}
                  title={a.title}
                  description={a.description}
                  icon={a.icon}
                  inputProps={{ type: "radio", value: a.value, ...register("aiAutonomy") }}
                />
              ))}
            </div>
            <GroupError message={errors.aiAutonomy?.message} />
          </fieldset>

          <fieldset>
            <legend className="mb-1 text-sm font-medium text-foreground">Capabilities</legend>
            <p className="mb-3 text-xs text-muted-foreground">
              Enable the tools your AI employee can use. You can change these later.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {CAPABILITIES.map((c) => (
                <OptionCard
                  key={c.value}
                  title={c.title}
                  description={c.description}
                  icon={c.icon}
                  inputProps={{ type: "checkbox", value: c.value, ...register("aiCapabilities") }}
                />
              ))}
            </div>
            <GroupError message={errors.aiCapabilities?.message} />
          </fieldset>
        </div>
        <div className="mt-8">
          <WizardNav onBack={prev} />
        </div>
      </StepShell>
    </form>
  );
}
