"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Info, MailCheck } from "lucide-react";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/features/auth/validation/schemas";
import { useAuth, authErrorMessage } from "@/features/auth/hooks/use-auth";
import { AuthCard } from "../components/auth-card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export function ForgotPasswordForm() {
  const { forgotPassword, capabilities } = useAuth();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await forgotPassword.mutateAsync(values);
    } catch {
      /* surfaced via isError */
    }
  });

  // The active backend has no password-reset endpoint. Say so plainly rather
  // than presenting a form whose submission can only fail.
  if (!capabilities.forgotPassword) {
    return (
      <AuthCard
        title="Password reset unavailable"
        description="This deployment doesn't support self-service password resets yet."
        footer={
          <>
            Back to{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              sign in
            </Link>
          </>
        }
      >
        <Alert variant="info" icon={Info}>
          Contact your administrator to have your password reset.
        </Alert>
        <Button variant="outline" className="w-full" href="/login">
          Back to sign in
        </Button>
      </AuthCard>
    );
  }

  if (forgotPassword.isSuccess) {
    return (
      <AuthCard
        title="Check your email"
        description="Follow the link in the email to reset your password."
        footer={
          <>
            Back to{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              sign in
            </Link>
          </>
        }
      >
        <Alert variant="success" icon={MailCheck}>
          If an account exists for <span className="font-medium">{getValues("email")}</span>, a reset link is on its way.
        </Alert>
        <Button variant="outline" className="w-full" href="/login">
          Back to sign in
        </Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Reset your password"
      description="Enter your email and we'll send you a reset link."
      footer={
        <>
          Remembered it?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {forgotPassword.isError ? (
          <Alert variant="error" icon={AlertCircle}>
            {authErrorMessage(forgotPassword.error)}
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

        <Button type="submit" className="w-full" disabled={forgotPassword.isPending}>
          {forgotPassword.isPending ? <Spinner /> : null}
          Send reset link
        </Button>
      </form>
    </AuthCard>
  );
}
