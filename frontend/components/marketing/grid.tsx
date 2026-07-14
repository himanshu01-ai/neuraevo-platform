import { cn } from "@/lib/utils";

/**
 * Subtle decorative grid overlay. Lines use the `--border` token (never a
 * hardcoded color) and fade out via a radial mask. Purely decorative.
 */
export function Grid({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("absolute inset-0 opacity-60", className)}
      style={{
        backgroundImage:
          "linear-gradient(to right, hsl(var(--border) / 0.7) 1px, transparent 1px), linear-gradient(to bottom, hsl(var(--border) / 0.7) 1px, transparent 1px)",
        backgroundSize: "64px 64px",
        maskImage: "radial-gradient(ellipse 75% 55% at 50% 0%, #000 40%, transparent 100%)",
        WebkitMaskImage: "radial-gradient(ellipse 75% 55% at 50% 0%, #000 40%, transparent 100%)",
      }}
    />
  );
}
