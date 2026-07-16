import type { EmployeeConfiguration } from "@/services/employees";
import { EXECUTION_MODE_LABEL, PRIORITY_LABEL, PRIORITY_TONE } from "@/types/domain";
import { Badge } from "@/components/ui/badge";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { AUTONOMY_META, TONE_META } from "../models/employee-configuration";
import { cn } from "@/lib/utils";

export interface ProfileConfigurationProps {
  configuration: EmployeeConfiguration;
  className?: string;
}

/**
 * How this employee is set up to behave. Read-only: the builder is where
 * configuration changes, so this surface states it and links nowhere.
 */
export function ProfileConfiguration({ configuration, className }: ProfileConfigurationProps) {
  const autonomy = AUTONOMY_META[configuration.autonomy];
  const tone = TONE_META[configuration.tone];

  return (
    <div className={cn("space-y-4", className)}>
      <div className="grid gap-3 sm:grid-cols-2">
        {[autonomy, tone].map((choice) => {
          const Icon = choice.icon;
          return (
            <div key={choice.value} className="flex items-start gap-3 rounded-md border bg-background p-3">
              <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{choice.label}</p>
                <p className="text-xs text-muted-foreground">{choice.description}</p>
              </div>
            </div>
          );
        })}
      </div>

      <dl className="space-y-2.5 text-sm">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Execution mode</dt>
          <dd className="font-medium text-foreground">
            {EXECUTION_MODE_LABEL[configuration.executionMode]}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Priority</dt>
          <dd>
            <Badge variant={TONE_VARIANT[PRIORITY_TONE[configuration.priority]]}>
              {PRIORITY_LABEL[configuration.priority]}
            </Badge>
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Pause for approval</dt>
          <dd className="font-medium text-foreground">{configuration.requireApproval ? "Yes" : "No"}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Language</dt>
          <dd className="font-medium uppercase text-foreground">{configuration.language}</dd>
        </div>
      </dl>
    </div>
  );
}
