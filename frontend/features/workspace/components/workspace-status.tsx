import { cn } from "@/lib/utils";

/**
 * Desktop status bar. Presentational shell chrome only (readiness indicator +
 * shortcut hint + version) — no live data, no analytics.
 */
export function WorkspaceStatus({ className }: { className?: string }) {
  return (
    <footer
      className={cn(
        "flex h-8 shrink-0 items-center justify-between border-t bg-card/40 px-4 text-xs text-muted-foreground",
        className
      )}
    >
      <span className="flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-success" aria-hidden="true" />
        Ready
      </span>
      <div className="hidden items-center gap-4 sm:flex">
        <span className="flex items-center gap-1.5">
          <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">⌘B</kbd>
          Toggle sidebar
        </span>
        <span className="font-mono">v0.17.3</span>
      </div>
    </footer>
  );
}
