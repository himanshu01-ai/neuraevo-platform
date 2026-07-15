"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { companySchema, type CompanyValues } from "../validation/schemas";
import { COMPANY_SIZES, INDUSTRIES } from "./options";
import { useOnboarding } from "../hooks/use-onboarding";
import { StepShell } from "../components/step-shell";
import { WizardNav } from "../components/wizard-nav";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export function CompanyStep() {
  const { data, updateData, next, prev } = useOnboarding();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CompanyValues>({
    resolver: zodResolver(companySchema),
    defaultValues: {
      companyName: data.companyName ?? "",
      companySize: data.companySize ?? "",
      industry: data.industry ?? "",
    },
  });

  const onSubmit = handleSubmit((values) => {
    updateData(values);
    next();
  });

  return (
    <form onSubmit={onSubmit} noValidate>
      <StepShell
        eyebrow="Company"
        title="Where does it work?"
        description="Context about your organization helps your AI employee prioritize the right work."
      >
        <div className="space-y-4">
          <Field label="Company name" error={errors.companyName?.message} required>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                autoComplete="organization"
                placeholder="Acme Inc."
                aria-invalid={invalid}
                aria-describedby={describedBy}
                {...register("companyName")}
              />
            )}
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Company size" error={errors.companySize?.message} required>
              {({ id, describedBy, invalid }) => (
                <Select id={id} aria-invalid={invalid} aria-describedby={describedBy} {...register("companySize")}>
                  <option value="">Select size</option>
                  {COMPANY_SIZES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <Field label="Industry" error={errors.industry?.message} required>
              {({ id, describedBy, invalid }) => (
                <Select id={id} aria-invalid={invalid} aria-describedby={describedBy} {...register("industry")}>
                  <option value="">Select industry</option>
                  {INDUSTRIES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </div>
        <div className="mt-8">
          <WizardNav onBack={prev} />
        </div>
      </StepShell>
    </form>
  );
}
