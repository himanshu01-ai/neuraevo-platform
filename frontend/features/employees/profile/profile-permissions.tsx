import type { EmployeePermission } from "@/services/employees";
import { PERMISSION_LEVEL_LABEL, PERMISSION_TONE } from "@/services/employees";
import { Badge } from "@/components/ui/badge";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { PERMISSION_META } from "../models/employee-permissions";
import { cn } from "@/lib/utils";

export interface ProfilePermissionsProps {
  permissions: readonly EmployeePermission[];
  className?: string;
}

/**
 * What this employee is allowed to do, and where it has to stop and ask.
 *
 * Blocked permissions are listed rather than hidden: the value of this screen is
 * seeing the whole boundary at once, including the parts that are closed. A
 * permission follows its capability — grant the capability in the builder and
 * the permission opens with it.
 */
export function ProfilePermissions({ permissions, className }: ProfilePermissionsProps) {
  return (
    <ul className={cn("space-y-1", className)}>
      {permissions.map((permission) => {
        const meta = PERMISSION_META[permission.id];
        const tone = PERMISSION_TONE[permission.level];
        const isBlocked = permission.level === "BLOCKED";

        return (
          <li key={permission.id} className="flex items-start justify-between gap-3 rounded-md px-2 py-2">
            <div className="min-w-0">
              <p className={cn("text-sm font-medium", isBlocked ? "text-muted-foreground" : "text-foreground")}>
                {meta.label}
              </p>
              <p className="text-xs text-muted-foreground">{meta.description}</p>
            </div>
            <Badge variant={TONE_VARIANT[tone]} className="shrink-0">
              <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone])} />
              {PERMISSION_LEVEL_LABEL[permission.level]}
            </Badge>
          </li>
        );
      })}
    </ul>
  );
}
