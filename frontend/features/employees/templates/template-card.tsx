"use client";

import { memo } from "react";
import type { EmployeeTemplateSummary } from "@/services/employees";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CapabilityChips } from "../components/capability-chips";
import { EmployeeAvatar } from "../components/employee-avatar";
import { ROLE_META } from "../models/employee-roles";

export interface TemplateCardProps {
  template: EmployeeTemplateSummary;
  onUse: (id: string) => void;
  isPending?: boolean;
}

/** One template: the job it's shaped for, what it comes with, and a way to start. */
export const TemplateCard = memo(function TemplateCard({
  template,
  onUse,
  isPending = false,
}: TemplateCardProps) {
  return (
    <div className="flex flex-col rounded-lg border bg-card p-5 shadow-sm transition-all hover:border-primary/30 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <EmployeeAvatar name={template.name} accent={template.accent} glyph={template.glyph} size="md" />
        <Badge variant="outline">{template.category}</Badge>
      </div>

      <h3 className="mt-4 text-sm font-semibold text-foreground">{template.name}</h3>
      <p className="mt-1 flex-1 text-sm leading-relaxed text-muted-foreground">{template.description}</p>

      <p className="mt-3 text-xs text-muted-foreground">{ROLE_META[template.role].label}</p>
      <CapabilityChips capabilities={template.capabilities} max={6} className="mt-2" />

      <div className="mt-4 border-t pt-4">
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => onUse(template.id)}
          disabled={isPending}
        >
          {isPending ? "Opening…" : "Use template"}
        </Button>
      </div>
    </div>
  );
});
