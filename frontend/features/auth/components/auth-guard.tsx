"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { useSessionBootstrap } from "@/features/auth/hooks/use-auth";
import { SessionLoading } from "./session-loading";

/** Route guard: requires an authenticated session, else redirects to /login. */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const status = useAuthStore((s) => s.status);
  useSessionBootstrap();

  useEffect(() => {
    if (status === "unauthenticated") router.replace("/login");
  }, [status, router]);

  if (status === "authenticated") return <>{children}</>;
  return <SessionLoading label="Checking your session…" />;
}
