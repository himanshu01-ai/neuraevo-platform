import { cn } from "@/lib/utils";

function initials(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p.charAt(0).toUpperCase()).join("") || "?";
}

/** Initials avatar (no images/backend). Accent-tinted, theme-aware. */
export function Avatar({ name, className }: { name?: string | null; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-8 shrink-0 select-none items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary",
        className
      )}
    >
      {initials(name)}
    </span>
  );
}
