import type { Metadata } from "next";
import { AuthGuard } from "@/features/auth/components/auth-guard";
import { WorkspaceLoading } from "./workspace-loading";

export const metadata: Metadata = { title: "Workspace" };

export default function WorkspacePage() {
  return (
    <AuthGuard>
      <WorkspaceLoading />
    </AuthGuard>
  );
}
