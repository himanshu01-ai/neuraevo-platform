"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle } from "lucide-react";
import { verifyEmailSchema, type VerifyEmailValues } from "@/features/auth/validation/schemas";
import { useAuth, authErrorMessage } from "@/features/auth/hooks/use-auth";
import { AuthCard } from "../components/auth-card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

const DEMO_EMAIL = "user@neuraevo.com";

export function VerifyEmailForm() {
  const router = useRouter();
  const { verifyEmail, forgotPassword, user } = useAuth();
  const email = user?.email ?? DEMO_EMAIL;
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<VerifyEmailValues>({
    resolver: zodResolver(verifyEmailSchema),
    defaultValues: { code: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await verifyEmail.mutateAsync({ email, code: values.code });
      router.replace("/onboarding");
    } catch {
      /* surfaced via isError */
    }
  });

  return (
    <AuthCard
      title="Verify your email"
      description={
        <>
          Enter the 6-digit code we sent to{" "}
          <span className="font-medium text-foreground">{email}</span>.
        </>
      }
      footer={
        <>
          Back to{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {verifyEmail.isError ? (
          <Alert variant="error" icon={AlertCircle}>
            {authErrorMessage(verifyEmail.error)}
          </Alert>
        ) : null}

        <Field
          label="Verification code"
          error={errors.code?.message}
          description="Demo: any 6 digits verify; 000000 shows an error."
          required
        >
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="123456"
              className="text-center font-mono text-lg tracking-[0.5em]"
              aria-invalid={invalid}
              aria-describedby={describedBy}
              {...register("code")}
            />
          )}
        </Field>

        <Button type="submit" className="w-full" disabled={verifyEmail.isPending}>
          {verifyEmail.isPending ? <Spinner /> : null}
          Verify email
        </Button>

        <p className="text-center text-sm text-muted-foreground" aria-live="polite">
          {forgotPassword.isSuccess ? (
            "A new code has been sent."
          ) : (
            <>
              Didn&apos;t get it?{" "}
              <button
                type="button"
                onClick={() => forgotPassword.mutate({ email })}
                disabled={forgotPassword.isPending}
                className="font-medium text-primary hover:underline disabled:opacity-50"
              >
                Resend code
              </button>
            </>
          )}
        </p>
      </form>
    </AuthCard>
  );
}
