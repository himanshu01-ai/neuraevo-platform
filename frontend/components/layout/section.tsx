import { cn } from "@/lib/utils";

export interface SectionProps extends React.HTMLAttributes<HTMLElement> {
  /** Anchor id (also used as the aria-labelledby target base). */
  id?: string;
}

/**
 * Semantic page section with the design-system's vertical rhythm. Scroll-margin
 * offsets the sticky header so anchor navigation lands cleanly.
 */
export function Section({ id, className, children, ...props }: SectionProps) {
  return (
    <section
      id={id}
      className={cn("scroll-mt-20 py-16 sm:py-24 lg:py-28", className)}
      {...props}
    >
      {children}
    </section>
  );
}
