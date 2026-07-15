"use client";

import { NavItem } from "./nav-item";
import type { NavGroup, NavItem as NavItemType } from "./nav-config";

export interface WorkspaceNavigationProps {
  groups: NavGroup[];
  footer?: NavItemType[];
  isActive: (href: string) => boolean;
  collapsed?: boolean;
  onNavigate?: () => void;
}

/** The grouped nav list, shared by the desktop Sidebar and the MobileDrawer. */
export function WorkspaceNavigation({
  groups,
  footer,
  isActive,
  collapsed = false,
  onNavigate,
}: WorkspaceNavigationProps) {
  return (
    <nav className="flex flex-1 flex-col gap-6" aria-label="Workspace sections">
      <div className="flex flex-1 flex-col gap-6">
        {groups.map((group) => (
          <div key={group.id} className="space-y-1">
            {!collapsed ? (
              <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
                {group.label}
              </p>
            ) : null}
            <ul className="space-y-0.5">
              {group.items.map((item) => (
                <li key={item.id}>
                  <NavItem item={item} active={isActive(item.href)} collapsed={collapsed} onNavigate={onNavigate} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {footer ? (
        <ul className="space-y-0.5 border-t pt-3">
          {footer.map((item) => (
            <li key={item.id}>
              <NavItem item={item} active={isActive(item.href)} collapsed={collapsed} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
      ) : null}
    </nav>
  );
}
