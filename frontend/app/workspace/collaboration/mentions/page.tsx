import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Mentions" };

const MentionsScreen = dynamic(() => import("@/features/collaboration").then((m) => m.MentionsScreen), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={4} />
    </WorkspaceContent>
  ),
});

export default function CollaborationMentionsPage() {
  return <MentionsScreen />;
}
