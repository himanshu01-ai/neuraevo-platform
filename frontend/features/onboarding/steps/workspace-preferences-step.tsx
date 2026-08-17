"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTheme } from "next-themes";
import { workspacePreferencesSchema, type WorkspacePreferencesValues } from "../validation/schemas";
import { DENSITIES, NOTIFICATIONS, THEMES } from "./options";
import { useOnboarding } from "../hooks/use-onboarding";
import { useMounted } from "@/hooks/use-mounted";
import { StepShell } from "../components/step-shell";
import { WizardNav } from "../components/wizard-nav";
import { OptionCard } from "@/components/ui/option-card";

export function WorkspacePreferencesStep() {
  const { data, updateData, next, prev } = useOnboarding();
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<WorkspacePreferencesValues>({
    resolver: zodResolver(workspacePreferencesSchema),
    defaultValues: {
      density: data.density ?? "comfortable",
      notifications: data.notifications ?? ["approvals", "completions"],
    },
  });

  const onSubmit = handleSubmit((values) => {
    updateData(values);
    next();
  });

  return (
    <form onSubmit={onSubmit} noValidate>
      <StepShell
        eyebrow="Workspace"
        title="Make it yours"
        description="Set the look and the signals you want from your workspace."
      >
        <div className="space-y-8">
          <fieldset>
            <legend className="mb-3 text-sm font-medium text-foreground">Appearance</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              {THEMES.map((t) => (
                <OptionCard
                  key={t.value}
                  title={t.title}
                  inputProps={{
                    type: "radio",
                    name: "theme",
                    value: t.value,
                    checked: mounted ? theme === t.value : false,
                    onChange: () => setTheme(t.value),
                  }}
                />
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-3 text-sm font-medium text-foreground">Layout density</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              {DENSITIES.map((d) => (
                <OptionCard
                  key={d.value}
                  title={d.title}
                  description={d.description}
                  inputProps={{ type: "radio", value: d.value, ...register("density") }}
                />
              ))}
            </div>
            {errors.density ? (
              <p role="alert" className="mt-2 text-xs font-medium text-destructive">
                {errors.density.message}
              </p>
            ) : null}
          </fieldset>

          <fieldset>
            <legend className="mb-3 text-sm font-medium text-foreground">Notifications</legend>
            <div className="grid gap-3">
              {NOTIFICATIONS.map((n) => (
                <OptionCard
                  key={n.value}
                  title={n.title}
                  description={n.description}
                  inputProps={{ type: "checkbox", value: n.value, ...register("notifications") }}
                />
              ))}
            </div>
          </fieldset>
        </div>
        <div className="mt-8">
          <WizardNav onBack={prev} />
        </div>
      </StepShell>
    </form>
  );
}
