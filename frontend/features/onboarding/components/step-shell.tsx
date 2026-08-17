import type { ReactNode } from "react";

export interface StepShellProps {
  eyebrow?: string;
  title: string;
  description?: string;
  children: ReactNode;
}

/** Consistent header + body layout for each onboarding step. */
export function StepShell({ eyebrow, title, description, children }: StepShellProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">{eyebrow}</p>
        ) : null}
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {children}
    </div>
  );
}
