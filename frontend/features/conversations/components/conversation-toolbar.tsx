"use client";

import {
  Archive,
  ArchiveRestore,
  AudioLines,
  Ellipsis,
  History,
  PanelRight,
  Pin,
  PinOff,
  Plus,
  Search,
  Settings2,
  SquareArrowOutUpRight,
  Users,
} from "lucide-react";
import type { ConversationDetail } from "@/services/conversations";
import { CONVERSATION_STATUS_LABEL, CONVERSATION_STATUS_TONE } from "@/services/conversations";
import type { EmployeeSummary } from "@/services/employees";
import { useConversationStore } from "@/store/conversations";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { TONE_VARIANT } from "@/components/ui/status-badge";
import { roleLabel } from "@/features/employees/models/employee-roles";
import { cn } from "@/lib/utils";

export interface ConversationToolbarProps {
  conversation: ConversationDetail | null;
  employees: readonly EmployeeSummary[];
  onCreate: (employeeId: string) => void;
  onTogglePinned: () => void;
  onToggleShared: () => void;
  onToggleArchived: () => void;
  isBusy: boolean;
  isCreateDisabled: boolean;
  className?: string;
}

/**
 * The bar across the top of the workspace: who the selected conversation is
 * with and its standing, plus the actions — new conversation (pick the
 * employee), pin, share, archive/restore, and the side trips to details,
 * search, history and settings. The context panel toggle lives here too, so
 * the panel can be summoned back from anywhere.
 */
export function ConversationToolbar({
  conversation,
  employees,
  onCreate,
  onTogglePinned,
  onToggleShared,
  onToggleArchived,
  isBusy,
  isCreateDisabled,
  className,
}: ConversationToolbarProps) {
  const contextPanelOpen = useConversationStore((s) => s.contextPanelOpen);
  const setContextPanelOpen = useConversationStore((s) => s.setContextPanelOpen);
  const archived = conversation?.status === "archived";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-lg border bg-card px-3 py-2 shadow-sm",
        className
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        {conversation ? (
          <>
            <Avatar name={conversation.employee.employeeName} className="size-9" />
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-foreground">{conversation.title}</h2>
              <p className="truncate text-xs text-muted-foreground">
                {conversation.employee.employeeName} · {conversation.employee.roleTitle}
              </p>
            </div>
            <Badge
              variant={TONE_VARIANT[CONVERSATION_STATUS_TONE[conversation.status]]}
              className="shrink-0"
            >
              {CONVERSATION_STATUS_LABEL[conversation.status]}
            </Badge>
            {conversation.shared ? (
              <Badge variant="outline" className="hidden shrink-0 sm:inline-flex">
                <Users className="size-3" aria-hidden="true" />
                Shared
              </Badge>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Pick a conversation, or start a new one.</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {/* Voice is the primary interaction — offered prominently on a selected
            conversation, opening the full-screen voice session. */}
        {conversation ? (
          <Button
            size="sm"
            href={`/voice/${conversation.id}`}
            aria-label={`Start a voice session with ${conversation.employee.employeeName}`}
            className="mr-1"
          >
            <AudioLines className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Voice</span>
          </Button>
        ) : null}

        <DropdownMenu
          menuLabel="New conversation"
          align="end"
          items={employees.map((employee) => ({
            key: employee.id,
            label: `${employee.name} — ${roleLabel(employee.role, employee.customRole)}`,
            onSelect: () => onCreate(employee.id),
          }))}
          renderTrigger={(props) => (
            <Button {...props} size="sm" disabled={isBusy || isCreateDisabled}>
              <Plus className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">New conversation</span>
              <span className="sr-only sm:hidden">New conversation</span>
            </Button>
          )}
        />

        {conversation ? (
          <DropdownMenu
            menuLabel={`Actions for ${conversation.title}`}
            align="end"
            items={[
              {
                key: "pin",
                label: conversation.pinned ? "Unpin" : "Pin",
                icon: conversation.pinned ? PinOff : Pin,
                onSelect: onTogglePinned,
              },
              {
                key: "share",
                label: conversation.shared ? "Stop sharing" : "Share with teammates",
                icon: Users,
                onSelect: onToggleShared,
              },
              {
                key: "archive",
                label: archived ? "Restore" : "Archive",
                icon: archived ? ArchiveRestore : Archive,
                destructive: !archived,
                onSelect: onToggleArchived,
              },
              {
                key: "open",
                label: "Open details",
                icon: SquareArrowOutUpRight,
                href: `/workspace/conversations/${conversation.id}`,
              },
              { key: "settings", label: "Settings", icon: Settings2, href: "/workspace/conversations/settings" },
            ]}
            renderTrigger={(props) => (
              <Button
                {...props}
                variant="ghost"
                size="icon"
                disabled={isBusy}
                aria-label={`Actions for ${conversation.title}`}
                className="text-muted-foreground"
              >
                <Ellipsis className="size-4" aria-hidden="true" />
              </Button>
            )}
          />
        ) : null}

        <Button
          variant="ghost"
          size="icon"
          href="/workspace/conversations/search"
          aria-label="Search conversations"
          className="text-muted-foreground"
        >
          <Search className="size-4" aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          href="/workspace/conversations/history"
          aria-label="Conversation history"
          className="text-muted-foreground"
        >
          <History className="size-4" aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setContextPanelOpen(!contextPanelOpen)}
          aria-label={contextPanelOpen ? "Hide context panel" : "Show context panel"}
          aria-pressed={contextPanelOpen}
          className={cn("text-muted-foreground", contextPanelOpen && "bg-primary/10 text-primary")}
        >
          <PanelRight className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
