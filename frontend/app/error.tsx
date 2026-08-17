"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Client-side error boundary hook — reporting is wired in a later sprint.
  }, [error]);

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="inline-flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertTriangle aria-hidden />
      </div>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-foreground">Something went wrong</h1>
        <p className="max-w-md text-muted-foreground">
          An unexpected error occurred while loading this page. You can try again.
        </p>
      </div>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
