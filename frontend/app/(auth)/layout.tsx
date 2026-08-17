import type { Metadata } from "next";
import { AuthLayout } from "@/features/auth/components/auth-layout";

export const metadata: Metadata = {
  title: "Account",
};

export default function AuthGroupLayout({ children }: { children: React.ReactNode }) {
  return <AuthLayout>{children}</AuthLayout>;
}
