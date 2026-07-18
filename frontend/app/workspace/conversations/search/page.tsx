import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { MessagesSquare } from "lucide-react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Search conversations" };

const ConversationSearch = dynamic(
  () => import("@/features/conversations").then((m) => m.ConversationSearch),
  { loading: () => <LoadingState rows={4} /> }
);

export default function ConversationSearchPage() {
  return (
    <WorkspaceContent>
      <WorkspaceHeader
        title="Search conversations"
        description="Find what was said, referenced, or generated — across every thread."
        actions={
          <Button variant="outline" href="/workspace/conversations">
            <MessagesSquare className="size-4" aria-hidden="true" />
            Back to workspace
          </Button>
        }
      />
      <div className="mt-6 max-w-4xl">
        <ConversationSearch />
      </div>
    </WorkspaceContent>
  );
}
