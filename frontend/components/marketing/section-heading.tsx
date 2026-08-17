import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface SectionHeadingProps {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: "center" | "left";
  className?: string;
}

/** Reusable eyebrow + title + description block for section headers. */
export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "center",
  className,
}: SectionHeadingProps) {
  return (
    <div className={cn("space-y-4", align === "center" && "mx-auto max-w-2xl text-center", className)}>
      {eyebrow ? <Badge variant="primary">{eyebrow}</Badge> : null}
      <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">{title}</h2>
      {description ? <p className="text-md text-muted-foreground">{description}</p> : null}
    </div>
  );
}
