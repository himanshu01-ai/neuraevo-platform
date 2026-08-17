import { forwardRef } from "react";
import { cn } from "@/lib/utils";

/** Multi-line text primitive. Mirrors <Input>; reflects invalid via `aria-invalid`. */
export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, rows = 3, ...props }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        "flex w-full rounded-sm border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors",
        "placeholder:text-muted-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
        "disabled:cursor-not-allowed disabled:opacity-40",
        "aria-[invalid=true]:border-destructive aria-[invalid=true]:focus-visible:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";
