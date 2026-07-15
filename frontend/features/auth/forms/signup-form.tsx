"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle } from "lucide-react";
import { signupSchema, type SignupValues } from "@/features/auth/validation/schemas";
import { useAuth, authErrorMessage } from "@/features/auth/hooks/use-auth";
import { AuthCard } from "../components/auth-card";
import { PasswordInput } from "../components/password-input";
import { PasswordStrengthMeter } from "../components/password-strength-meter";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export function SignupForm() {
  const router = useRouter();
  const { signup } = useAuth();
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { name: "", email: "", password: "", confirmPassword: "", terms: false },
  });

  const password = watch("password");

  const onSubmit = handleSubmit(async (values) => {
    try {
      await signup.mutateAsync({ name: values.name, email: values.email, password: values.password });
      router.replace("/onboarding");
    } catch {
      /* surfaced via signup.isError */
    }
  });

  return (
    <AuthCard
      title="Create your account"
      description="Set up your AI employee in a few minutes."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {signup.isError ? (
          <Alert variant="error" icon={AlertCircle}>
            {authErrorMessage(signup.error, "Unable to create your account.")}
          </Alert>
        ) : null}

        <Field label="Full name" error={errors.name?.message} required>
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              autoComplete="name"
              placeholder="Ada Lovelace"
              aria-invalid={invalid}
              aria-describedby={describedBy}
              {...register("name")}
            />
          )}
        </Field>

        <Field label="Email" error={errors.email?.message} required>
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              aria-invalid={invalid}
              aria-describedby={describedBy}
              {...register("email")}
            />
          )}
        </Field>

        <div className="space-y-2">
          <Field label="Password" error={errors.password?.message} required>
            {({ id, describedBy, invalid }) => (
              <PasswordInput
                id={id}
                autoComplete="new-password"
                placeholder="••••••••"
                aria-invalid={invalid}
                aria-describedby={describedBy}
                {...register("password")}
              />
            )}
          </Field>
          <PasswordStrengthMeter value={password} />
        </div>

        <Field label="Confirm password" error={errors.confirmPassword?.message} required>
          {({ id, describedBy, invalid }) => (
            <PasswordInput
              id={id}
              autoComplete="new-password"
              placeholder="••••••••"
              aria-invalid={invalid}
              aria-describedby={describedBy}
              {...register("confirmPassword")}
            />
          )}
        </Field>

        <div className="space-y-1.5">
          <label className="flex cursor-pointer items-start gap-2 text-sm text-muted-foreground">
            <Checkbox className="mt-0.5" aria-invalid={Boolean(errors.terms)} {...register("terms")} />
            <span>
              I agree to the{" "}
              <Link href="#" className="font-medium text-primary hover:underline">
                Terms
              </Link>{" "}
              and{" "}
              <Link href="#" className="font-medium text-primary hover:underline">
                Privacy Policy
              </Link>
              .
            </span>
          </label>
          {errors.terms ? (
            <p role="alert" className="text-xs font-medium text-destructive">
              {errors.terms.message}
            </p>
          ) : null}
        </div>

        <Button type="submit" className="w-full" disabled={signup.isPending}>
          {signup.isPending ? <Spinner /> : null}
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
