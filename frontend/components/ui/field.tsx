import { useId, type ReactNode } from "react";
import { Label } from "./label";
import { cn } from "@/lib/utils";

interface FieldRenderProps {
  id: string;
  describedBy: string | undefined;
  invalid: boolean;
}

export interface FieldProps {
  label: string;
  error?: string;
  description?: string;
  required?: boolean;
  className?: string;
  /** Render-prop that wires the control to the label/description/error a11y ids. */
  children: (props: FieldRenderProps) => ReactNode;
}

/**
 * Accessible form field: associates a label, optional description, and error
 * message with its control via `htmlFor` / `aria-describedby` / `aria-invalid`.
 */
export function Field({ label, error, description, required, className, children }: FieldProps) {
  const id = useId();
  const descId = `${id}-desc`;
  const errId = `${id}-err`;
  const describedBy =
    [description ? descId : null, error ? errId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>
        {label}
        {required ? (
          <span className="text-destructive" aria-hidden="true">
            {" "}
            *
          </span>
        ) : null}
      </Label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {description && !error ? (
        <p id={descId} className="text-xs text-muted-foreground">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={errId} role="alert" className="text-xs font-medium text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
