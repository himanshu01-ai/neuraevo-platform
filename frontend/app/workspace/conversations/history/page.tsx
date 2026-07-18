import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { MessagesSquare } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Conversation history" };

// History is a side trip from the workspace, so it loads on demand.
const ConversationHistory = dynamic(
  () => import("@/features/conversations").then((m) => m.ConversationHistory),
  { loading: () => <LoadingState rows={4} /> }
);

export default function ConversationHistoryPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Conversation history"
        description="Every conversation on record — active, archived, pinned, and shared."
        actions={
          <Button variant="outline" href="/workspace/conversations">
            <MessagesSquare className="size-4" aria-hidden="true" />
            Back to workspace
          </Button>
        }
      />
      <div className="mt-6 max-w-4xl">
        <ConversationHistory />
      </div>
    </WorkspaceContent>
  );
}
