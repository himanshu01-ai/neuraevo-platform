import { cn } from "@/lib/utils";

export interface ProgressProps {
  /** 0–100. */
  value: number;
  className?: string;
  label?: string;
}

/** Determinate progress bar with a smoothly animated fill. */
export function Progress({ value, className, label }: ProgressProps) {
  const v = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(v)}
      aria-label={label}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
    >
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
        style={{ width: `${v}%` }}
      />
    </div>
  );
}
