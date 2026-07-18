import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetPasswordForm } from "@/features/auth/forms/reset-password-form";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Choose a new password" };

export default function ResetPasswordPage() {
  return (
    // The form reads `?token=` from the reset link, so it needs a Suspense
    // boundary above it — without one, the search params would opt the whole
    // route out of static rendering.
    <Suspense fallback={<LoadingState rows={3} />}>
      <ResetPasswordForm />
    </Suspense>
  );
}

