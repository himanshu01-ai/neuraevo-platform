"use client";

import { Plus, ListChecks, Bot, Workflow } from "lucide-react";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** "Quick Create" menu in the top bar. Destinations open in the workspace. */
export function QuickActions({ className }: { className?: string }) {
  return (
    <DropdownMenu
      menuLabel="Create"
      align="end"
      items={[
        { key: "task", label: "New task", icon: ListChecks, href: "/workspace/tasks" },
        { key: "employee", label: "New AI employee", icon: Bot, href: "/workspace/ai-employees" },
        { key: "workflow", label: "New workflow", icon: Workflow, href: "/workspace/workflows" },
      ]}
      renderTrigger={(p) => (
        <button {...p} type="button" className={cn(buttonVariants({ size: "sm" }), className)}>
          <Plus className="size-4" aria-hidden="true" />
          <span className="hidden sm:inline">Create</span>
        </button>
      )}
    />
  );
}
