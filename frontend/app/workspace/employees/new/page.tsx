import type { Metadata } from "next";
import dynamic from "next/dynamic";
import { Suspense } from "react";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { LoadingState } from "@/components/ui/loading-state";

export const metadata: Metadata = { title: "New employee" };

const NewEmployeeBuilder = dynamic(() => import("@/features/employees").then((m) => m.NewEmployeeBuilder), {
  loading: () => (
    <WorkspaceContent>
      <LoadingState rows={6} />
    </WorkspaceContent>
  ),
});

const Fallback = () => (
  <WorkspaceContent>
    <LoadingState rows={6} />
  </WorkspaceContent>
);

export default function NewEmployeePage() {
  return (
    // The builder reads `?template=` to seed the draft, so it needs a Suspense
    // boundary above it — without one, the search params would opt the whole
    // route out of static rendering.
    <Suspense fallback={<Fallback />}>
      <NewEmployeeBuilder />
    </Suspense>
  );
}
