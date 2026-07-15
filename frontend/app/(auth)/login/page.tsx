import type { Metadata } from "next";
import { GuestGuard } from "@/features/auth/components/guest-guard";
import { LoginForm } from "@/features/auth/forms/login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <GuestGuard>
      <LoginForm />
    </GuestGuard>
  );
}
