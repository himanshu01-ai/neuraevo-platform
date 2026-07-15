"use client";

import { LogOut, Settings, User, CircleHelp } from "lucide-react";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { Avatar } from "@/components/ui/avatar";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { cn } from "@/lib/utils";

/** User profile menu: identity header + account links + sign out. */
export function UserMenu({ className }: { className?: string }) {
  const { user, logout } = useAuth();
  const name = user?.name ?? "Account";
  const email = user?.email ?? "";

  return (
    <DropdownMenu
      menuLabel="Account"
      align="end"
      header={
        <div className="-mx-1 -mt-1 mb-1 border-b px-3 py-2.5">
          <p className="truncate text-sm font-medium text-foreground">{name}</p>
          {email ? <p className="truncate text-xs text-muted-foreground">{email}</p> : null}
        </div>
      }
      items={[
        { key: "profile", label: "Profile", icon: User, href: "/workspace/settings" },
        { key: "settings", label: "Settings", icon: Settings, href: "/workspace/settings" },
        { key: "help", label: "Help", icon: CircleHelp, href: "/workspace/help" },
        {
          key: "logout",
          label: "Sign out",
          icon: LogOut,
          destructive: true,
          onSelect: () => {
            void logout();
          },
        },
      ]}
      renderTrigger={(p) => (
        <button
          {...p}
          type="button"
          aria-label="Account menu"
          className={cn(
            "inline-flex items-center gap-2 rounded-md p-1 pr-2 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            className
          )}
        >
          <Avatar name={user?.name} />
          <span className="hidden max-w-32 truncate text-sm font-medium text-foreground md:inline">{name}</span>
        </button>
      )}
    />
  );
}
