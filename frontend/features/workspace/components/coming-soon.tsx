import { Construction } from "lucide-react";
import { WorkspaceContent } from "./workspace-content";
import { WorkspaceHeader } from "./workspace-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { ALL_NAV_ITEMS } from "../navigation/nav-config";

function sectionTitle(segments: string[]): string {
  const href = `/workspace/${segments.join("/")}`;
  const known = ALL_NAV_ITEMS.find((i) => i.href === href);
  if (known) return known.label;
  const last = segments[segments.length - 1] ?? "Section";
  return last
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** In-shell placeholder for workspace sections not yet built (future sprints). */
export function ComingSoon({ segments }: { segments: string[] }) {
  const title = sectionTitle(segments);
  return (
    <WorkspaceContent>
      <WorkspaceHeader title={title} description="This section isn't available yet." />
      <div className="mt-8 rounded-lg border bg-card shadow-sm">
        <EmptyState
          icon={Construction}
          title={`${title} is coming soon`}
          description="This part of the workspace is under construction and will arrive in a future release."
          action={
            <Button variant="outline" href="/workspace">
              Back to home
            </Button>
          }
        />
      </div>
    </WorkspaceContent>
  );
}
