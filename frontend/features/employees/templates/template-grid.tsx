"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorState } from "@/components/ui/error-state";
import { EmployeeCardGridLoading } from "../components/employee-loading-state";
import { useEmployeeTemplates } from "../hooks/use-employees";
import { TemplateCard } from "./template-card";

/**
 * The template browser. Choosing one hands its id to the builder, which loads it
 * and fills the draft — the grid itself never touches the builder's state, so
 * arriving at `/new?template=…` from anywhere behaves identically.
 */
export function TemplateGrid() {
  const router = useRouter();
  const query = useEmployeeTemplates();
  const [pendingId, setPendingId] = useState<string | null>(null);

  if (query.isPending) return <EmployeeCardGridLoading />;

  if (query.isError) {
    return (
      <ErrorState
        title="Couldn't load templates"
        description="The templates couldn't be loaded. Try again in a moment."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const handleUse = (id: string) => {
    setPendingId(id);
    router.push(`/workspace/employees/new?template=${id}`);
  };

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {query.data.map((template) => (
        <TemplateCard
          key={template.id}
          template={template}
          onUse={handleUse}
          isPending={pendingId === template.id}
        />
      ))}
    </div>
  );
}
