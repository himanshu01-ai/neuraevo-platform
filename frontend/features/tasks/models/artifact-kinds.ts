import { Code, FileText, Folder, Mail, ScrollText, Table, type LucideIcon } from "lucide-react";
import { ARTIFACT_KINDS, type ArtifactKind } from "@/services/tasks";

/**
 * What each artifact kind is and how it looks. Neutral chips — colour carries
 * status in this system, and an artifact doesn't have one.
 */

export interface ArtifactMeta {
  kind: ArtifactKind;
  label: string;
  icon: LucideIcon;
  /** How the preview should be read when there is one. */
  isMonospace: boolean;
}

export const ARTIFACT_META: Record<ArtifactKind, ArtifactMeta> = {
  document: { kind: "document", label: "Document", icon: FileText, isMonospace: false },
  code: { kind: "code", label: "Code", icon: Code, isMonospace: true },
  file: { kind: "file", label: "File", icon: Folder, isMonospace: true },
  email: { kind: "email", label: "Email", icon: Mail, isMonospace: false },
  report: { kind: "report", label: "Report", icon: Table, isMonospace: false },
  log: { kind: "log", label: "Log", icon: ScrollText, isMonospace: true },
};

/** Every artifact kind in canonical order. */
export const ARTIFACT_LIST: readonly ArtifactMeta[] = ARTIFACT_KINDS.map((kind) => ARTIFACT_META[kind]);
