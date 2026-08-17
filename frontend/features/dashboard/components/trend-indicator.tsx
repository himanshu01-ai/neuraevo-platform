import { Minus, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import type { Trend, TrendDirection } from "@/services/dashboard";
import { cn } from "@/lib/utils";

const TREND_ICON: Record<TrendDirection, LucideIcon> = {
  up: TrendingUp,
  down: TrendingDown,
  flat: Minus,
  none: Minus,
};

/**
 * The trend slot on an overview card. Nothing here is computed — the platform
 * exposes no analytics yet, so every trend arrives as a `none` placeholder and
 * renders as a quiet line. Direction is styled neutrally on purpose: whether
 * "up" is good depends on the metric, and this component doesn't get to decide.
 */
export function TrendIndicator({ trend, className }: { trend: Trend; className?: string }) {
  const Icon = TREND_ICON[trend.direction];
  const isPlaceholder = trend.direction === "none";

  return (
    <p
      className={cn(
        "flex items-center gap-1 text-xs",
        isPlaceholder ? "text-muted-foreground/60" : "text-muted-foreground",
        className
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {trend.label}
    </p>
  );
}
