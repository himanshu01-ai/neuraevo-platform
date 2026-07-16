"use client";

import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { WelcomeHeader } from "./welcome-header";
import { OverviewWidget } from "../widgets/overview-widget";
import { QuickActionsWidget } from "../widgets/quick-actions-widget";
import { RecentTasksWidget } from "../widgets/recent-tasks-widget";
import { WorkflowWidget } from "../widgets/workflow-widget";
import { AIEmployeesWidget } from "../widgets/ai-employees-widget";
import { ApprovalWidget } from "../widgets/approval-widget";
import { MemoryWidget } from "../widgets/memory-widget";
import { NotificationWidget } from "../widgets/notification-widget";
import { HealthWidget } from "../widgets/health-widget";
import { SuggestionWidget } from "../widgets/suggestion-widget";

const ACTIVITY_HEADING_ID = "dashboard-activity-heading";

/**
 * The workspace dashboard. Composition only — every widget owns its own data,
 * states, and refresh, so this file just places them and staggers the reveal.
 *
 * Heading order is h1 (welcome) → h2 (section) → h3 (panel). The activity
 * region's h2 is visually hidden because each panel inside carries its own
 * visible title.
 */
export function DashboardHome() {
  return (
    <WorkspaceContent>
      <div className="space-y-8">
        <Reveal>
          <WelcomeHeader />
        </Reveal>

        <Reveal delay={0.05}>
          <OverviewWidget />
        </Reveal>

        <Reveal delay={0.1}>
          <QuickActionsWidget />
        </Reveal>

        <section aria-labelledby={ACTIVITY_HEADING_ID}>
          <h2 id={ACTIVITY_HEADING_ID} className="sr-only">
            Workspace activity and status
          </h2>

          {/* 3/2 rather than 2/1: a third-width rail leaves the panel headers
              too narrow for a title alongside their controls. */}
          <div className="grid gap-6 lg:grid-cols-5">
            {/* min-w-0: grid items default to min-width:auto, which lets the
                panels' content push the column past the viewport on mobile. */}
            <div className="min-w-0 space-y-6 lg:col-span-3">
              <Reveal delay={0.05}>
                <RecentTasksWidget />
              </Reveal>
              <Reveal delay={0.1}>
                <WorkflowWidget />
              </Reveal>
              <Reveal delay={0.15}>
                <AIEmployeesWidget />
              </Reveal>
            </div>

            <div className="min-w-0 space-y-6 lg:col-span-2">
              <Reveal delay={0.05}>
                <ApprovalWidget />
              </Reveal>
              <Reveal delay={0.1}>
                <MemoryWidget />
              </Reveal>
              <Reveal delay={0.15}>
                <NotificationWidget />
              </Reveal>
            </div>
          </div>

          <Reveal className="mt-6">
            <HealthWidget />
          </Reveal>
        </section>

        <Reveal>
          <SuggestionWidget />
        </Reveal>
      </div>
    </WorkspaceContent>
  );
}
