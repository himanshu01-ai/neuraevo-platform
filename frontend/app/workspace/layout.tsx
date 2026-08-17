import type { Metadata } from "next";
import { AuthGuard } from "@/features/auth/components/auth-guard";
import { WorkspaceShell } from "@/layouts/workspace-shell";

export const metadata: Metadata = {
  title: { default: "Workspace", template: "%s · NeuraEvo" },
};

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <WorkspaceShell>{children}</WorkspaceShell>
    </AuthGuard>
  );
}
