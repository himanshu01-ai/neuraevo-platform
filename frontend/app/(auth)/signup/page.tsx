import type { Metadata } from "next";
import { GuestGuard } from "@/features/auth/components/guest-guard";
import { SignupForm } from "@/features/auth/forms/signup-form";

export const metadata: Metadata = { title: "Create account" };

export default function SignupPage() {
  return (
    <GuestGuard>
      <SignupForm />
    </GuestGuard>
  );
}
