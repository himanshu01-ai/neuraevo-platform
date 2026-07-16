"use client";

import { Plus } from "lucide-react";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";

/**
 * The dashboard's page header. Greets by first name once the session has
 * hydrated; the workspace only renders behind an authenticated AuthGuard, so
 * there is no server/client greeting mismatch.
 */
export function WelcomeHeader() {
  const { user } = useAuth();
  const firstName = user?.name?.split(" ")[0];

  return (
    <WorkspaceHeader
      title={firstName ? `Welcome back, ${firstName}` : "Welcome to your workspace"}
      description="Your AI employee is ready. Delegate work and track it here."
      actions={
        <Button href="/workspace/tasks">
          <Plus className="size-4" aria-hidden="true" />
          Delegate a task
        </Button>
      }
    />
  );
}
