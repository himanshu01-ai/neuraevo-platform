"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LayoutTemplate } from "lucide-react";
import { workflowsService } from "@/services/workflows";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useBuilderStore } from "@/store/workflow";
import { useWorkflowTemplates } from "../hooks/use-workflows";
import { WorkflowCardGridLoading } from "../components/workflow-loading-state";
import { TemplateCard } from "./template-card";

/**
 * The template browser.
 *
 * Choosing a template fetches its full definition, loads it into the builder
 * draft as a *new, unsaved* workflow, and opens the builder. It never writes
 * anything: you get an editable copy, and nothing is created until you save.
 */
export function TemplateGrid() {
  const router = useRouter();
  const query = useWorkflowTemplates();
  const resetDraft = useBuilderStore((s) => s.resetDraft);
  const loadGraph = useBuilderStore((s) => s.loadGraph);
  const setDescription = useBuilderStore((s) => s.setDescription);
  const setNotice = useBuilderStore((s) => s.setNotice);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const handleUse = async (id: string) => {
    setPendingId(id);
    try {
      const template = await workflowsService.template(id);
      resetDraft(template.name);
      setDescription(template.description);
      loadGraph(template.graph, template.settings);
      router.push("/workspace/workflows/new");
    } catch {
      setNotice("Couldn't open that template.");
      setPendingId(null);
    }
  };

  if (query.isError) {
    return (
      <ErrorState
        title="Couldn't load templates"
        description="The template list couldn't be loaded. Try again in a moment."
        onRetry={() => void query.refetch()}
      />
    );
  }

  if (query.isPending) return <WorkflowCardGridLoading count={8} />;

  if (query.data.length === 0) {
    return (
      <EmptyState
        icon={LayoutTemplate}
        title="No templates"
        description="Templates will appear here once the platform provides them."
      />
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {query.data.map((template) => (
        <TemplateCard
          key={template.id}
          template={template}
          onUse={(id) => void handleUse(id)}
          isPending={pendingId === template.id}
        />
      ))}
    </div>
  );
}
