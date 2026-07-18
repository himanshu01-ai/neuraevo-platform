import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Notifications" };

const NotificationCenter = dynamic(
  () => import("@/features/collaboration").then((m) => m.NotificationCenter),
  {
    loading: () => (
      <WorkspaceContent>
        <LoadingState rows={6} />
      </WorkspaceContent>
    ),
  }
);

export default function CollaborationPage() {
  return <NotificationCenter />;
}
