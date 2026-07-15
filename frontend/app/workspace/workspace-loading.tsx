"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useOnboardingStore } from "@/store/auth";
import { useMounted } from "@/hooks/use-mounted";
import { SessionLoading } from "@/features/auth/components/session-loading";

/**
 * Workspace is a loading/redirect handoff only (the real workspace ships in a
 * later sprint). Authenticated users who haven't onboarded are sent to the
 * wizard; otherwise a session-loading screen holds the entry point.
 */
export function WorkspaceLoading() {
  const router = useRouter();
  const mounted = useMounted();
  const finished = useOnboardingStore((s) => s.finished);

  useEffect(() => {
    if (mounted && !finished) router.replace("/onboarding");
  }, [mounted, finished, router]);

  return <SessionLoading label="Preparing your workspace…" />;
}
