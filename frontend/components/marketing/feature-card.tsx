import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FeatureCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  className?: string;
}

/**
 * Reusable capability/feature card. Icon chip + title + description with a
 * quiet hover lift (CSS-only, so it stays a lightweight server component).
 */
export function FeatureCard({ title, description, icon: Icon, className }: FeatureCardProps) {
  return (
    <div
      className={cn(
        "group relative h-full rounded-lg border bg-card p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-primary/30 hover:shadow-md",
        className
      )}
    >
      <div className="mb-4 inline-flex size-11 items-center justify-center rounded-md bg-primary/10 text-primary">
        <Icon className="size-5" aria-hidden />
      </div>
      <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}
