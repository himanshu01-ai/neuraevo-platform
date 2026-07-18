"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle } from "lucide-react";
import { loginSchema, type LoginValues } from "@/features/auth/validation/schemas";
import { useAuth, authErrorMessage } from "@/features/auth/hooks/use-auth";
import { AuthCard } from "../components/auth-card";
import { PasswordInput } from "../components/password-input";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export function LoginForm() {
  const router = useRouter();
  const { login, capabilities } = useAuth();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", remember: false },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login.mutateAsync({ email: values.email, password: values.password });
      router.replace("/workspace");
    } catch {
      /* surfaced via login.isError */
    }
  });

  return (
    <AuthCard
      title="Welcome back"
      description="Sign in to your NeuraEvo workspace."
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="font-medium text-primary hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {login.isError ? (
          <Alert variant="error" icon={AlertCircle}>
            {authErrorMessage(login.error, "Unable to sign in.")}
          </Alert>
        ) : null}

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

        <Field label="Password" error={errors.password?.message} required>
          {({ id, describedBy, invalid }) => (
            <PasswordInput
              id={id}
              autoComplete="current-password"
              placeholder="••••••••"
              aria-invalid={invalid}
              aria-describedby={describedBy}
              {...register("password")}
            />
          )}
        </Field>

        <div className="flex items-center justify-between">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
            <Checkbox {...register("remember")} />
            Remember me
          </label>
          {/* Hidden unless the active backend can actually reset a password. */}
          {capabilities.forgotPassword ? (
            <Link href="/forgot-password" className="text-sm font-medium text-primary hover:underline">
              Forgot password?
            </Link>
          ) : null}
        </div>

        <Button type="submit" className="w-full" disabled={login.isPending}>
          {login.isPending ? <Spinner /> : null}
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
