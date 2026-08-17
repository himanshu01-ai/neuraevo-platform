import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { Brain } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Panel } from "@/features/workspace/panels/panel";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Documents" };

const ImportPanel = dynamic(() => import("@/features/memory").then((m) => m.ImportPanel), {
  loading: () => <LoadingState rows={4} />,
});

const DocumentList = dynamic(() => import("@/features/memory").then((m) => m.DocumentList), {
  loading: () => <LoadingState rows={4} />,
});

export default function DocumentsPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Documents"
        description="Knowledge that arrived as a file, and how to bring more in."
        actions={
          <Button variant="outline" href="/workspace/memory">
            <Brain className="size-4" aria-hidden="true" />
            Browse knowledge
          </Button>
        }
      />

      <div className="mt-6 space-y-6">
        <Panel title="Import" description="Add what your employees should already know.">
          <ImportPanel />
        </Panel>

        <section>
          <h2 className="text-sm font-semibold text-foreground">Documents</h2>
          <div className="mt-3">
            <DocumentList />
          </div>
        </section>
      </div>
    </WorkspaceContent>
  );
}
