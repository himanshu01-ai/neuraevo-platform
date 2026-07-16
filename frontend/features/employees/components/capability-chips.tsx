import type { EmployeeCapability } from "@/services/employees";
import { CAPABILITY_META } from "../models/employee-capabilities";
import { cn } from "@/lib/utils";

export interface CapabilityChipsProps {
  capabilities: readonly EmployeeCapability[];
  /** Chips shown before the rest collapse into a count. */
  max?: number;
  className?: string;
}

/**
 * An employee's capabilities as a row of glyphs. Icons are decorative; each
 * carries an sr-only name, so the row reads as a list of capability names rather
 * than a row of unlabelled pictures.
 *
 * Chips are neutral: colour carries status in this system, and a capability
 * isn't one.
 */
export function CapabilityChips({ capabilities, max = 5, className }: CapabilityChipsProps) {
  if (capabilities.length === 0) {
    return <p className={cn("text-xs text-muted-foreground", className)}>No capabilities yet</p>;
  }

  const shown = capabilities.slice(0, max);
  const overflow = capabilities.length - shown.length;

  return (
    <ul className={cn("flex flex-wrap items-center gap-1", className)}>
      {shown.map((capability) => {
        const meta = CAPABILITY_META[capability];
        const Icon = meta.icon;
        return (
          <li
            key={capability}
            className="inline-flex size-6 items-center justify-center rounded-sm bg-muted text-muted-foreground"
          >
            <Icon className="size-3.5" aria-hidden="true" />
            <span className="sr-only">{meta.label}</span>
          </li>
        );
      })}
      {overflow > 0 ? (
        <li className="inline-flex h-6 items-center rounded-sm bg-muted px-1.5 text-xs font-medium text-muted-foreground">
          +{overflow}
          <span className="sr-only"> more capabilities</span>
        </li>
      ) : null}
    </ul>
  );
}
