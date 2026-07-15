"use client";

import Link from "next/link";
import {
  ListChecks,
  Blocks,
  Sparkles,
  Activity,
  Workflow,
  Bot,
  LayoutDashboard,
  Plus,
  ArrowRight,
} from "lucide-react";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { Panel } from "../panels/panel";
import { WorkspaceCard } from "../panels/workspace-card";
import { WorkspaceContent } from "./workspace-content";
import { WorkspaceHeader } from "./workspace-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/motion/reveal";

const SUGGESTIONS = [
  {
    title: "Delegate your first task",
    description: "Describe the work; your AI employee plans and executes it.",
    icon: ListChecks,
    href: "/workspace/tasks",
  },
  {
    title: "Connect an integration",
    description: "Give your AI employee access to the tools you already use.",
    icon: Blocks,
    href: "/workspace/integrations",
  },
  {
    title: "Explore capabilities",
    description: "See what your AI employee can do across the platform.",
    icon: Sparkles,
    href: "/workspace/ai-employees",
  },
];

const QUICK_ACTIONS = [
  { label: "New task", icon: ListChecks, href: "/workspace/tasks" },
  { label: "New workflow", icon: Workflow, href: "/workspace/workflows" },
  { label: "Invite a teammate", icon: Plus, href: "/workspace/settings" },
];

/** Premium placeholder home for the workspace. Empty states + suggestions only
 *  — no fake data, analytics, or execution. */
export function WorkspaceHome() {
  const { user } = useAuth();
  const firstName = user?.name?.split(" ")[0];

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkspaceHeader
          title={firstName ? `Welcome back, ${firstName}` : "Welcome to your workspace"}
          description="Your AI employee is ready. Delegate work and track it here."
          actions={
            <Button href="/workspace/tasks">
              <Plus className="size-4" aria-hidden="true" />
              Delegate a task
            </Button>
          }
        />
      </Reveal>

      <Reveal delay={0.05}>
        <section aria-labelledby="suggested-heading" className="mt-8">
          <h2 id="suggested-heading" className="sr-only">
            Suggested actions
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {SUGGESTIONS.map((s) => (
              <WorkspaceCard key={s.title} title={s.title} description={s.description} icon={s.icon} href={s.href} />
            ))}
          </div>
        </section>
      </Reveal>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Reveal delay={0.1}>
            <Panel title="Recent activity" description="What your AI employee has done recently.">
              <EmptyState
                icon={Activity}
                title="No activity yet"
                description="Once you delegate work, its progress and results show up here."
              />
            </Panel>
          </Reveal>
          <Reveal delay={0.15}>
            <Panel title="Workspace overview">
              <EmptyState
                icon={LayoutDashboard}
                title="Your overview will appear here"
                description="Status, throughput, and health surface once work is running."
              />
            </Panel>
          </Reveal>
        </div>

        <div className="space-y-6">
          <Reveal delay={0.1}>
            <Panel title="Quick actions">
              <ul className="space-y-1">
                {QUICK_ACTIONS.map((action) => (
                  <li key={action.label}>
                    <Link
                      href={action.href}
                      className="flex items-center justify-between rounded-md px-2 py-2 text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="flex items-center gap-2.5">
                        <action.icon className="size-4 text-muted-foreground" aria-hidden="true" />
                        {action.label}
                      </span>
                      <ArrowRight className="size-4 text-muted-foreground/60" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </Panel>
          </Reveal>
          <Reveal delay={0.15}>
            <Panel title="Pinned workflows">
              <EmptyState
                compact
                icon={Workflow}
                title="No pinned workflows"
                description="Pin workflows for quick access."
                action={
                  <Button variant="outline" size="sm" href="/workspace/workflows">
                    Browse workflows
                  </Button>
                }
              />
            </Panel>
          </Reveal>
          <Reveal delay={0.2}>
            <Panel title="Favorite AI employees">
              <EmptyState
                compact
                icon={Bot}
                title="No favorites yet"
                description="Star an AI employee to find it fast."
                action={
                  <Button variant="outline" size="sm" href="/workspace/ai-employees">
                    Browse
                  </Button>
                }
              />
            </Panel>
          </Reveal>
        </div>
      </div>
    </WorkspaceContent>
  );
}
