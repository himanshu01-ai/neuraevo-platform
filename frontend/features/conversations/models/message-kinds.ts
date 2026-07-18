import {
  Bell,
  Bot,
  Braces,
  Brain,
  FileCode2,
  FileImage,
  FileText,
  Files,
  ListChecks,
  MessageSquareText,
  Package,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Workflow,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type {
  AttachmentKind,
  ConversationArtifactKind,
  MessageKind,
  SuggestionKind,
} from "@/services/conversations";

/**
 * Presentation vocabulary for the thread: icon and label per message kind,
 * attachment kind, artifact kind and suggestion kind. UI concern only — the
 * service layer names the kinds, this file says how each one looks. Declared
 * once so a card in the thread and a chip in the composer can never disagree
 * about what a workflow looks like.
 */

export interface KindMeta {
  label: string;
  icon: LucideIcon;
}

export const MESSAGE_KIND_META: Record<Exclude<MessageKind, "text">, KindMeta> = {
  approval_request: { label: "Approval request", icon: ShieldCheck },
  artifact: { label: "Artifact", icon: Package },
  workflow_reference: { label: "Workflow", icon: Workflow },
  task_reference: { label: "Task", icon: ListChecks },
  memory_reference: { label: "Memory", icon: Brain },
  notification: { label: "Notification", icon: Bell },
};

export const ATTACHMENT_KIND_META: Record<AttachmentKind, KindMeta> = {
  document: { label: "Document", icon: FileText },
  image: { label: "Image", icon: FileImage },
  code: { label: "Code", icon: FileCode2 },
  report: { label: "Report", icon: ScrollText },
  workflow: { label: "Workflow", icon: Workflow },
  task: { label: "Task", icon: ListChecks },
  memory: { label: "Memory", icon: Brain },
  artifact: { label: "Artifact", icon: Package },
};

export const ARTIFACT_KIND_META: Record<ConversationArtifactKind, KindMeta> = {
  document: { label: "Generated document", icon: FileText },
  code: { label: "Generated code", icon: Braces },
  report: { label: "Generated report", icon: ScrollText },
  workflow: { label: "Generated workflow", icon: Workflow },
  summary: { label: "Generated summary", icon: Files },
};

export const SUGGESTION_KIND_META: Record<SuggestionKind, KindMeta> = {
  prompt: { label: "Suggested prompt", icon: MessageSquareText },
  task: { label: "Recent task", icon: ListChecks },
  workflow: { label: "Recent workflow", icon: Workflow },
  memory: { label: "Recent memory", icon: Brain },
  employee: { label: "Recent employee", icon: Bot },
  action: { label: "Quick action", icon: Zap },
};

/** The voice affordance's icon lives with its siblings, ready for Sprint 20+. */
export const VOICE_PLACEHOLDER_ICON: LucideIcon = Sparkles;
