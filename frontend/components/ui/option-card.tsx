import type { LucideIcon } from "lucide-react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface OptionCardProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  /** Props for the underlying native radio/checkbox input (accepts RHF `register()`). */
  inputProps: React.ComponentProps<"input">;
  className?: string;
}

/**
 * A selectable card backed by a native radio or checkbox (accessible + keyboard
 * operable). Selection styling is driven purely by the input's `:checked` state
 * via the `has-[:checked]` variant, so it stays a controlled DOM primitive.
 */
export function OptionCard({ title, description, icon: Icon, inputProps, className }: OptionCardProps) {
  return (
    <label
      className={cn(
        "group relative flex cursor-pointer items-start gap-3 rounded-lg border bg-card p-4 text-left shadow-sm transition-all",
        "hover:border-primary/40",
        "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background",
        "has-[:checked]:border-primary has-[:checked]:bg-primary/5",
        "has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50",
        className
      )}
    >
      <input className="peer sr-only" {...inputProps} />
      {Icon ? (
        <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="size-4" aria-hidden="true" />
        </span>
      ) : null}
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-foreground">{title}</span>
        {description ? (
          <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{description}</span>
        ) : null}
      </span>
      <span
        aria-hidden="true"
        className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full border border-border text-transparent transition-colors peer-checked:border-primary peer-checked:bg-primary peer-checked:text-primary-foreground"
      >
        <Check className="size-3" strokeWidth={3} />
      </span>
    </label>
  );
}
