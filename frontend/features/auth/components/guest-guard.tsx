"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { useSessionBootstrap } from "@/features/auth/hooks/use-auth";
import { SessionLoading } from "./session-loading";

/** Route guard for auth pages: redirects already-signed-in users to /workspace. */
export function GuestGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const status = useAuthStore((s) => s.status);
  useSessionBootstrap();

  useEffect(() => {
    if (status === "authenticated") router.replace("/workspace");
  }, [status, router]);

  if (status === "authenticated") return <SessionLoading label="Redirecting…" />;
  return <>{children}</>;
}
