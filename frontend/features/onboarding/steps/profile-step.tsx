"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { profileSchema, type ProfileValues } from "../validation/schemas";
import { ROLES } from "./options";
import { useOnboarding } from "../hooks/use-onboarding";
import { StepShell } from "../components/step-shell";
import { WizardNav } from "../components/wizard-nav";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export function ProfileStep() {
  const { data, updateData, next, prev } = useOnboarding();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { fullName: data.fullName ?? "", role: data.role ?? "" },
  });

  const onSubmit = handleSubmit((values) => {
    updateData(values);
    next();
  });

  return (
    <form onSubmit={onSubmit} noValidate>
      <StepShell
        eyebrow="Profile"
        title="Tell us about you"
        description="This personalizes how your AI employee addresses and works with you."
      >
        <div className="space-y-4">
          <Field label="Full name" error={errors.fullName?.message} required>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                autoComplete="name"
                placeholder="Ada Lovelace"
                aria-invalid={invalid}
                aria-describedby={describedBy}
                {...register("fullName")}
              />
            )}
          </Field>

          <Field label="Your role" error={errors.role?.message} required>
            {({ id, describedBy, invalid }) => (
              <Select id={id} aria-invalid={invalid} aria-describedby={describedBy} {...register("role")}>
                <option value="">Select your role</option>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <div className="mt-8">
          <WizardNav onBack={prev} />
        </div>
      </StepShell>
    </form>
  );
}
