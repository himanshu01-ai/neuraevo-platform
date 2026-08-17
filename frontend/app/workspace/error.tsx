"use client";

import { useEffect } from "react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { ErrorState } from "@/components/ui/error-state";

/**
 * Workspace-scoped error boundary.
 *
 * Without this, a render error in any workspace screen bubbles to the root
 * `app/error.tsx`, which replaces the whole document — taking the sidebar and
 * top bar with it and leaving the user with no way out but the back button.
 * Because a segment's `error.tsx` renders *inside* its parent layout, this
 * keeps the shell mounted: navigation stays usable and only the content region
 * reports the failure.
 *
 * Reuses `ErrorState`, the same component every screen's own query-error path
 * renders, so a boundary failure and a fetch failure look like one system.
 */
export default function WorkspaceError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Client-side error boundary hook — reporting is wired in a later sprint.
  }, [error]);

  return (
    <WorkspaceContent>
      <ErrorState
        title="This screen couldn't be loaded"
        description="Something went wrong rendering this part of your workspace. You can try again, or pick another section from the navigation."
        onRetry={reset}
        retryLabel="Try again"
      />
    </WorkspaceContent>
  );
}
