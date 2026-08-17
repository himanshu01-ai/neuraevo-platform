import { cn } from "@/lib/utils";

/** Loading placeholder. Matches the final content's shape to avoid layout shift. */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}
