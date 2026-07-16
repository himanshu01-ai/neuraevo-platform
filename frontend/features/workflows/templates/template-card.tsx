"use client";

import { memo } from "react";
import { LayoutTemplate } from "lucide-react";
import type { WorkflowTemplateSummary } from "@/services/workflows";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface TemplateCardProps {
  template: WorkflowTemplateSummary;
  onUse: (id: string) => void;
  isPending?: boolean;
}

/** One template: what it does, how big it is, and a way to start from it. */
export const TemplateCard = memo(function TemplateCard({ template, onUse, isPending = false }: TemplateCardProps) {
  return (
    <div className="flex flex-col rounded-lg border bg-card p-5 shadow-sm transition-all hover:border-primary/30 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary">
          <LayoutTemplate className="size-5" aria-hidden="true" />
        </span>
        <Badge variant="outline">{template.category}</Badge>
      </div>

      <h3 className="mt-4 text-sm font-semibold text-foreground">{template.name}</h3>
      <p className="mt-1 flex-1 text-sm leading-relaxed text-muted-foreground">{template.description}</p>

      <div className="mt-4 flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          {template.nodeCount === 0 ? "Empty canvas" : `${template.nodeCount} steps`}
        </span>
        <Button variant="outline" size="sm" onClick={() => onUse(template.id)} disabled={isPending}>
          {isPending ? "Opening…" : "Use template"}
        </Button>
      </div>
    </div>
  );
});
