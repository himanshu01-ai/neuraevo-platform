"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import {
  resourceCollaborationService,
  ResourceCollaborationError,
  COLLABORATION_ROLE_LABEL,
  type CollaborationResourceType,
  type ResourceParticipant,
} from "@/services/collaboration/resource";
import { Button } from "@/components/ui/button";

/** Where each resource type lives in the workspace, so a join can link onward. */
const RESOURCE_HREF: Record<CollaborationResourceType, (id: string) => string> = {
  conversation: (id) => `/workspace/conversations/${id}`,
  task: (id) => `/workspace/tasks/${id}`,
  workflow: (id) => `/workspace/workflows/${id}`,
  memory: (id) => `/workspace/memory/${id}`,
};

const RESOURCE_LABEL: Record<CollaborationResourceType, string> = {
  conversation: "conversation",
  task: "task",
  workflow: "workflow",
  memory: "memory",
};

type State =
  | { status: "redeeming" }
  | { status: "joined"; participant: ResourceParticipant }
  | { status: "error"; message: string };

/**
 * Share-link redemption. Opening `/collaboration/join/{token}` while signed in
 * makes the viewer a participant at the link's role, then offers a way through
 * to the resource. The redeem is idempotent, so a refresh or a second open is
 * harmless.
 */
export default function JoinPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const [state, setState] = useState<State>({ status: "redeeming" });
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current || !token) return;
    attempted.current = true;

    resourceCollaborationService
      .redeem(token)
      .then((participant) => setState({ status: "joined", participant }))
      .catch((error) => {
        const message =
          error instanceof ResourceCollaborationError
            ? error.message
            : "This link couldn't be opened.";
        setState({ status: "error", message });
      });
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      {state.status === "redeeming" ? (
        <>
          <Loader2 className="size-6 animate-spin text-primary" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">Opening your invitation…</p>
        </>
      ) : null}

      {state.status === "joined" ? (
        <>
          <h1 className="text-lg font-semibold text-foreground">You&apos;re in</h1>
          <p className="text-sm text-muted-foreground">
            You joined this {RESOURCE_LABEL[state.participant.resourceType]} as{" "}
            {COLLABORATION_ROLE_LABEL[state.participant.role].toLowerCase()}.
          </p>
          <Button
            href={RESOURCE_HREF[state.participant.resourceType](
              state.participant.resourceId
            )}
          >
            Open the {RESOURCE_LABEL[state.participant.resourceType]}
          </Button>
        </>
      ) : null}

      {state.status === "error" ? (
        <>
          <h1 className="text-lg font-semibold text-foreground">
            This link can&apos;t be opened
          </h1>
          <p className="text-sm text-muted-foreground">{state.message}</p>
          <Button href="/workspace" variant="outline">
            Back to workspace
          </Button>
        </>
      ) : null}
    </main>
  );
}
