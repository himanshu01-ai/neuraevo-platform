import { LogoMark } from "@/components/brand/logo";

/** Full-screen brand loader used while resolving the session or redirecting. */
export function SessionLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6 text-center">
      <LogoMark className="size-10 animate-pulse text-foreground" />
      <p className="text-sm text-muted-foreground" role="status" aria-live="polite">
        {label}
      </p>
    </div>
  );
}
