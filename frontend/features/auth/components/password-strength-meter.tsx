"use client";

import { getPasswordStrength } from "@/features/auth/validation/password-strength";
import { cn } from "@/lib/utils";

const TONE = ["bg-muted", "bg-destructive", "bg-warning", "bg-info", "bg-success"] as const;

/** Four-segment password strength indicator with a polite live label. */
export function PasswordStrengthMeter({ value }: { value: string }) {
  const { score, label } = getPasswordStrength(value);

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1" aria-hidden="true">
        {[1, 2, 3, 4].map((seg) => (
          <div
            key={seg}
            className={cn("h-1 flex-1 rounded-full transition-colors", seg <= score ? TONE[score] : "bg-muted")}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground" aria-live="polite">
        {value ? (
          <>
            Password strength: <span className="font-medium text-foreground">{label}</span>
          </>
        ) : (
          "Use 8+ characters with upper, lower, and a number."
        )}
      </p>
    </div>
  );
}
