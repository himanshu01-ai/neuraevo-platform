"use client";

import { memo } from "react";
import Link from "next/link";
import { WidgetShell } from "../components/widget-shell";
import { QUICK_ACTIONS } from "../models/quick-actions";

/**
 * Quick Actions — a navigation rail, nothing more. Each tile is a link.
 *
 * It goes through <WidgetShell> for a consistent header and to inherit the state
 * contract the moment these actions become data-driven, but it has no refresh
 * button: the list is a constant, so there is nothing to refetch and a refresh
 * control would be a lie.
 */
export const QuickActionsWidget = memo(function QuickActionsWidget() {
  return (
    <WidgetShell
      variant="bare"
      title="Quick actions"
      description="Jump straight to where the work happens."
      isLoading={false}
      isError={false}
      isEmpty={QUICK_ACTIONS.length === 0}
      empty={null}
    >
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-8">
        {QUICK_ACTIONS.map((action) => (
          <li key={action.id}>
            <Link
              href={action.href}
              className="group flex h-full flex-col items-start gap-2 rounded-lg border bg-card p-3 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="inline-flex size-8 items-center justify-center rounded-md bg-muted text-muted-foreground transition-colors group-hover:bg-primary/10 group-hover:text-primary">
                <action.icon className="size-4" aria-hidden="true" />
              </span>
              <span className="text-sm font-medium leading-snug text-foreground">{action.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </WidgetShell>
  );
});
