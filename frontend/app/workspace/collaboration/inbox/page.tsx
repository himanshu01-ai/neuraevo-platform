import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "Inbox" };

const NotificationInbox = dynamic(
  () => import("@/features/collaboration").then((m) => m.NotificationInbox),
  {
    loading: () => (
      <WorkspaceContent>
        <LoadingState rows={6} />
      </WorkspaceContent>
    ),
  }
);

export default function CollaborationInboxPage() {
  return <NotificationInbox />;
}
