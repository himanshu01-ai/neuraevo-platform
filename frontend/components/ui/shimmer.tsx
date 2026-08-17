import { cn } from "@/lib/utils";

/**
 * Shimmering placeholder block. A sweep reads as "loading" more clearly than a
 * pulse on dense surfaces; the global reduced-motion rule flattens it to a
 * static block.
 *
 * Sibling of <Skeleton> (which pulses). Both are domain-agnostic primitives.
 */
export function Shimmer({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cn("relative overflow-hidden rounded-md bg-muted", className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-foreground/10 to-transparent" />
    </div>
  );
}
