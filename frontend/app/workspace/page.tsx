import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

// Lazy-load the workspace home so the section is code-split from the shell.
const WorkspaceHome = dynamic(
  () => import("@/features/workspace/components/workspace-home").then((m) => m.WorkspaceHome),
  {
    loading: () => (
      <WorkspaceContent>
        <LoadingState rows={6} />
      </WorkspaceContent>
    ),
  }
);

export default function WorkspacePage() {
  return <WorkspaceHome />;
}
