"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import { AuthError } from "@/services/auth";
import { resetPasswordSchema, type ResetPasswordValues } from "@/features/auth/validation/schemas";
import { useAuth, authErrorMessage } from "@/features/auth/hooks/use-auth";
import { AuthCard } from "../components/auth-card";
import { PasswordInput } from "../components/password-input";
import { PasswordStrengthMeter } from "../components/password-strength-meter";
import { Field } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { ErrorState } from "@/components/ui/error-state";

/**
 * Choose a new password from an emailed reset link (`/reset-password?token=…`).
 *
 * The token is single-use and consumed by the backend, so there is nothing to
 * verify up front — a bad token only reveals itself on submit. Expired,
 * malformed, and already-used tokens all come back as one `invalid_token`,
 * matching the backend's deliberately indistinguishable reply, and are offered
 * a fresh link rather than a pointless retry.
 */
export function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const { resetPassword } = useAuth();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirmPassword: "" },
  });

  const password = watch("password");

  const onSubmit = handleSubmit(async (values) => {
    try {
      await resetPassword.mutateAsync({ token, newPassword: values.password });
    } catch {
      /* surfaced via resetPassword.isError */
    }
  });

  // Arrived without a token — the link was truncated or typed by hand.
  if (!token) {
    return (
      <AuthCard
        title="Reset your password"
        description="This link is missing its security token."
        footer={
          <>
            Remembered it?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </>
        }
      >
        <ErrorState
          title="This reset link is incomplete"
          description="Open the link directly from your email, or request a new one."
          action={
            <Button variant="outline" size="sm" href="/forgot-password">
              Request a new link
            </Button>
          }
        />
      </AuthCard>
    );
  }

  if (resetPassword.isSuccess) {
    return (
      <AuthCard
        title="Password changed"
        description="Your password has been updated."
        footer={
          <>
            Need help?{" "}
            <Link href="/forgot-password" className="font-medium text-primary hover:underline">
              Start over
            </Link>
          </>
        }
      >
        <Alert variant="success" icon={CheckCircle2}>
          You can now sign in with your new password. For your security, we signed you out
          everywhere else.
        </Alert>
        <Button className="w-full" href="/login">
          Go to Login
        </Button>
      </AuthCard>
    );
  }

  // A dead token can't be retried — send the user back for a fresh link.
  const tokenRejected =
    resetPassword.error instanceof AuthError &&
    resetPassword.error.code === "invalid_token";

  return (
    <AuthCard
      title="Choose a new password"
      description="Pick something you haven't used before."
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
        {resetPassword.isError ? (
          <Alert variant="error" icon={AlertCircle}>
            {authErrorMessage(resetPassword.error, "Unable to reset your password.")}
          </Alert>
        ) : null}

        <div className="space-y-2">
          <Field label="New password" error={errors.password?.message} required>
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

        {tokenRejected ? (
          <Button variant="outline" className="w-full" href="/forgot-password">
            Request a new link
          </Button>
        ) : (
          <Button type="submit" className="w-full" disabled={resetPassword.isPending}>
            {resetPassword.isPending ? <Spinner /> : null}
            Reset password
          </Button>
        )}
      </form>
    </AuthCard>
  );
}

