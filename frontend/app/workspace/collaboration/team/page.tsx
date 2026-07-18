import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Team activity" };

const TeamActivityScreen = dynamic(
  () => import("@/features/collaboration").then((m) => m.TeamActivityScreen),
  {
    loading: () => (
      <WorkspaceContent>
        <LoadingState rows={5} />
      </WorkspaceContent>
    ),
  }
);

export default function CollaborationTeamPage() {
  return <TeamActivityScreen />;
}
