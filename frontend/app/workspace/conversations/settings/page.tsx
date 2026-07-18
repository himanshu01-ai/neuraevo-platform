import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { MessagesSquare } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Conversation settings" };

const ConversationSettings = dynamic(
  () => import("@/features/conversations").then((m) => m.ConversationSettings),
  { loading: () => <LoadingState rows={4} /> }
);

export default function ConversationSettingsPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Conversation settings"
        description="Titles, pins, sharing, and the archive — managed per conversation."
        actions={
          <Button variant="outline" href="/workspace/conversations">
            <MessagesSquare className="size-4" aria-hidden="true" />
            Back to workspace
          </Button>
        }
      />
      <div className="mt-6">
        <ConversationSettings />
      </div>
    </WorkspaceContent>
  );
}
