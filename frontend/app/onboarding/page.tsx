import type { Metadata } from "next";
import { AuthGuard } from "@/features/auth/components/auth-guard";
import { OnboardingWizard } from "@/features/onboarding/components/onboarding-wizard";

export const metadata: Metadata = { title: "Set up your AI employee" };

export default function OnboardingPage() {
  return (
    <AuthGuard>
      <OnboardingWizard />
    </AuthGuard>
  );
}
