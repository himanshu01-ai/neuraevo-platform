import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { LayoutTemplate } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Workflow templates" };

// Templates are a side trip from the builder, so they load on demand.
const TemplateGrid = dynamic(() => import("@/features/workflows").then((m) => m.TemplateGrid), {
  loading: () => <LoadingState rows={6} />,
});

export default function WorkflowTemplatesPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Templates"
        description="Start from a workflow that already knows the shape of the job."
        actions={
          <Button variant="outline" href="/workspace/workflows">
            <LayoutTemplate className="size-4" aria-hidden="true" />
            All workflows
          </Button>
        }
      />
      <div className="mt-6">
        <TemplateGrid />
      </div>
    </WorkspaceContent>
  );
}
