import {
  BookMarked,
  Boxes,
  FileText,
  Lightbulb,
  ListOrdered,
  MessagesSquare,
  Scale,
  Shapes,
  type LucideIcon,
} from "lucide-react";
import { MEMORY_KINDS, type MemoryKind } from "@/services/memory";

/**
 * What each kind of memory is and how it looks.
 *
 * Kind chips are deliberately neutral. Colour in this system carries status, and
 * a memory already has two coloured facets (its retention and its status) —
 * tinting by kind as well would leave three colours arguing on one card. The
 * icon carries the kind instead.
 */

export interface MemoryKindMeta {
  kind: MemoryKind;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const MEMORY_KIND_META: Record<MemoryKind, MemoryKindMeta> = {
  document: {
    kind: "document",
    label: "Document",
    description: "Something written down in full.",
    icon: FileText,
  },
  conversation: {
    kind: "conversation",
    label: "Conversation",
    description: "What was said, and by whom.",
    icon: MessagesSquare,
  },
  knowledge: {
    kind: "knowledge",
    label: "Knowledge",
    description: "A fact worth keeping.",
    icon: Lightbulb,
  },
  procedure: {
    kind: "procedure",
    label: "Procedure",
    description: "How something gets done.",
    icon: ListOrdered,
  },
  template: {
    kind: "template",
    label: "Template",
    description: "A shape to fill in.",
    icon: Shapes,
  },
  artifact: {
    kind: "artifact",
    label: "Artifact",
    description: "Something a run produced.",
    icon: Boxes,
  },
  reference: {
    kind: "reference",
    label: "Reference",
    description: "A detail to look up.",
    icon: BookMarked,
  },
  policy: {
    kind: "policy",
    label: "Policy",
    description: "A rule that has to hold.",
    icon: Scale,
  },
};

/** Every kind in canonical order. */
export const MEMORY_KIND_LIST: readonly MemoryKindMeta[] = MEMORY_KINDS.map(
  (kind) => MEMORY_KIND_META[kind]
);
