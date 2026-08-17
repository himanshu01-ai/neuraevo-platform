"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link2, Loader2, Trash2, UserPlus } from "lucide-react";
import { employeeKeys, employeesService } from "@/services/employees";
import {
  COLLABORATION_ROLE_LABEL,
  type CollaborationResourceType,
  type CollaborationRole,
  type ResourceParticipant,
} from "@/services/collaboration/resource";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  useAddParticipant,
  useCreateShare,
  useParticipants,
  useResourceAccess,
  useResourceActivity,
  useRemoveParticipant,
  useRevokeShare,
  useShares,
  useUpdateParticipantRole,
} from "../hooks/use-resource-collaboration";

const ROLE_VARIANT: Record<CollaborationRole, "primary" | "info" | "outline"> = {
  owner: "primary",
  editor: "info",
  viewer: "outline",
};

/** Roles a link or participant may be granted — never owner. */
const GRANTABLE_ROLES: CollaborationRole[] = ["viewer", "editor"];

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h4>
  );
}

function ParticipantRow({
  participant,
  canManage,
  resourceType,
  resourceId,
}: {
  participant: ResourceParticipant;
  canManage: boolean;
  resourceType: CollaborationResourceType;
  resourceId: string;
}) {
  const updateRole = useUpdateParticipantRole(resourceType, resourceId);
  const remove = useRemoveParticipant(resourceType, resourceId);
  const manageable = canManage && !participant.isOwner && participant.id !== null;

  return (
    <li className="flex items-center gap-2.5 rounded-lg border bg-card p-2">
      <Avatar name={participant.name} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">
          {participant.name}
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {participant.participantType === "employee" ? "AI employee" : "Teammate"}
        </span>
      </span>

      {manageable ? (
        <Select
          aria-label={`Role for ${participant.name}`}
          value={participant.role}
          disabled={updateRole.isPending}
          onChange={(event) =>
            updateRole.mutate({
              participantId: participant.id as string,
              role: event.target.value as CollaborationRole,
            })
          }
          className="h-8 w-24 text-xs"
        >
          {GRANTABLE_ROLES.map((role) => (
            <option key={role} value={role}>
              {COLLABORATION_ROLE_LABEL[role]}
            </option>
          ))}
        </Select>
      ) : (
        <Badge variant={ROLE_VARIANT[participant.role]} className="shrink-0">
          {participant.isOwner ? "Owner" : COLLABORATION_ROLE_LABEL[participant.role]}
        </Badge>
      )}

      {manageable ? (
        <Button
          variant="ghost"
          size="icon"
          className="size-8 shrink-0 text-muted-foreground hover:text-destructive"
          aria-label={`Remove ${participant.name}`}
          disabled={remove.isPending}
          onClick={() => remove.mutate(participant.id as string)}
        >
          <Trash2 className="size-4" aria-hidden="true" />
        </Button>
      ) : null}
    </li>
  );
}

function AddEmployee({
  resourceType,
  resourceId,
  existingEmployeeIds,
}: {
  resourceType: CollaborationResourceType;
  resourceId: string;
  existingEmployeeIds: Set<string>;
}) {
  const [employeeId, setEmployeeId] = useState("");
  const [role, setRole] = useState<CollaborationRole>("viewer");
  const add = useAddParticipant(resourceType, resourceId);
  const employees = useQuery({
    queryKey: employeeKeys.lists,
    queryFn: employeesService.list,
    staleTime: 60_000,
  });

  const options = useMemo(
    () => (employees.data ?? []).filter((e) => !existingEmployeeIds.has(e.id)),
    [employees.data, existingEmployeeIds]
  );

  if (options.length === 0) return null;

  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (!employeeId) return;
        add.mutate(
          { participantType: "employee", employeeId, role },
          { onSuccess: () => setEmployeeId("") }
        );
      }}
    >
      <Select
        aria-label="AI employee to add"
        value={employeeId}
        onChange={(event) => setEmployeeId(event.target.value)}
        className="h-8 min-w-0 flex-1 text-xs"
      >
        <option value="">Add an AI employee…</option>
        {options.map((employee) => (
          <option key={employee.id} value={employee.id}>
            {employee.name}
          </option>
        ))}
      </Select>
      <Select
        aria-label="Role for the new AI employee"
        value={role}
        onChange={(event) => setRole(event.target.value as CollaborationRole)}
        className="h-8 w-24 text-xs"
      >
        {GRANTABLE_ROLES.map((r) => (
          <option key={r} value={r}>
            {COLLABORATION_ROLE_LABEL[r]}
          </option>
        ))}
      </Select>
      <Button type="submit" size="sm" disabled={!employeeId || add.isPending}>
        <UserPlus className="size-4" aria-hidden="true" />
        Add
      </Button>
      {add.isError ? (
        <p className="w-full text-xs text-destructive">
          {(add.error as Error).message}
        </p>
      ) : null}
    </form>
  );
}

function ShareLinks({
  resourceType,
  resourceId,
  enabled,
}: {
  resourceType: CollaborationResourceType;
  resourceId: string;
  enabled: boolean;
}) {
  const [role, setRole] = useState<CollaborationRole>("viewer");
  const [copied, setCopied] = useState<string | null>(null);
  const shares = useShares(resourceType, resourceId, enabled);
  const create = useCreateShare(resourceType, resourceId);
  const revoke = useRevokeShare(resourceType, resourceId);

  const activeShares = (shares.data ?? []).filter((s) => s.isActive);

  const copyLink = async (path: string) => {
    const url = typeof window !== "undefined" ? `${window.location.origin}${path}` : path;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(path);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      /* clipboard blocked — the link is still shown for manual copy */
    }
  };

  return (
    <section className="space-y-2">
      <SectionHeading>Share link</SectionHeading>
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate({ role });
        }}
      >
        <Select
          aria-label="Access the link grants"
          value={role}
          onChange={(event) => setRole(event.target.value as CollaborationRole)}
          className="h-8 w-28 text-xs"
        >
          {GRANTABLE_ROLES.map((r) => (
            <option key={r} value={r}>
              {COLLABORATION_ROLE_LABEL[r]} link
            </option>
          ))}
        </Select>
        <Button type="submit" size="sm" variant="outline" disabled={create.isPending}>
          <Link2 className="size-4" aria-hidden="true" />
          Create
        </Button>
      </form>

      {create.data ? (
        <div className="rounded-md border bg-muted/40 p-2">
          <p className="mb-1 text-xs text-muted-foreground">
            Anyone signed in who opens this link joins as {create.data.role}.
          </p>
          <div className="flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 text-xs">
              {create.data.path}
            </code>
            <Button size="sm" variant="ghost" onClick={() => copyLink(create.data!.path)}>
              {copied === create.data.path ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>
      ) : null}

      {activeShares.length > 0 ? (
        <ul className="space-y-1" aria-label="Active share links">
          {activeShares.map((share) => (
            <li
              key={share.id}
              className="flex items-center gap-2 rounded-md border bg-card px-2 py-1.5 text-xs"
            >
              <Badge variant={ROLE_VARIANT[share.role]}>{COLLABORATION_ROLE_LABEL[share.role]}</Badge>
              <span className="flex-1 text-muted-foreground">
                {share.expiresAt ? "Expires" : "No expiry"}
              </span>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-muted-foreground hover:text-destructive"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(share.id)}
              >
                Revoke
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function ActivityTimeline({
  resourceType,
  resourceId,
}: {
  resourceType: CollaborationResourceType;
  resourceId: string;
}) {
  const activity = useResourceActivity(resourceType, resourceId);
  const events = (activity.data ?? []).slice(0, 8);
  if (events.length === 0) return null;

  return (
    <section className="space-y-2">
      <SectionHeading>Recent activity</SectionHeading>
      <ul className="space-y-1.5" aria-label="Recent activity">
        {events.map((event) => (
          <li key={event.id} className="flex gap-2 text-xs">
            <span className="mt-1 size-1.5 shrink-0 rounded-full bg-primary/60" aria-hidden="true" />
            <span className="min-w-0">
              <span className="text-foreground">{event.actorName}</span>{" "}
              <span className="text-muted-foreground">{event.summary}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * The collaboration surface for one resource: who is on it, the links that let
 * others join, and what has happened. Every control is permission-gated by the
 * caller's effective role, resolved from the platform — a viewer sees the
 * roster and activity; only the owner manages participants and links.
 */
export function ResourceCollaborationPanel({
  resourceType,
  resourceId,
  className,
}: {
  resourceType: CollaborationResourceType;
  resourceId: string;
  className?: string;
}) {
  const access = useResourceAccess(resourceType, resourceId);
  const participants = useParticipants(resourceType, resourceId);
  const isOwner = access.data?.isOwner ?? false;

  const existingEmployeeIds = useMemo(
    () =>
      new Set(
        (participants.data ?? [])
          .filter((p) => p.employeeId)
          .map((p) => p.employeeId as string)
      ),
    [participants.data]
  );

  if (access.isLoading || participants.isLoading) {
    return (
      <div className={cn("flex items-center gap-2 p-2 text-sm text-muted-foreground", className)}>
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading collaboration…
      </div>
    );
  }

  if (access.isError || participants.isError) {
    return (
      <p className={cn("p-2 text-sm text-muted-foreground", className)}>
        Collaboration isn&apos;t available for this item.
      </p>
    );
  }

  const roster = participants.data ?? [];

  return (
    <div className={cn("space-y-5", className)}>
      <section className="space-y-2">
        <SectionHeading>Participants</SectionHeading>
        <ul className="space-y-1.5" aria-label="Participants">
          {roster.map((participant) => (
            <ParticipantRow
              key={participant.id ?? `owner-${participant.userId}`}
              participant={participant}
              canManage={isOwner}
              resourceType={resourceType}
              resourceId={resourceId}
            />
          ))}
        </ul>
        {isOwner ? (
          <AddEmployee
            resourceType={resourceType}
            resourceId={resourceId}
            existingEmployeeIds={existingEmployeeIds}
          />
        ) : null}
      </section>

      {isOwner ? (
        <ShareLinks resourceType={resourceType} resourceId={resourceId} enabled={isOwner} />
      ) : null}

      <ActivityTimeline resourceType={resourceType} resourceId={resourceId} />
    </div>
  );
}
