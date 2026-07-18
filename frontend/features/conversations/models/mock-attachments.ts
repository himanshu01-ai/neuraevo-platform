import type { Attachment } from "@/services/conversations";

/**
 * What the attach menu offers. Mock picks only — nothing uploads, and choosing
 * one stages a fixed reference the way a real picker would stage a file. File
 * attachments carry fixture sizes; platform references (workflow, task,
 * memory) reuse the same records the rest of the workspace shows.
 */
export const ATTACHABLE_FILES: Attachment[] = [
  {
    id: "att_file_1",
    kind: "document",
    name: "q3-planning-notes.docx",
    size: "36.7 KB",
    preview: "Q3 planning notes — priorities, owners, open questions.",
  },
  {
    id: "att_file_2",
    kind: "image",
    name: "pricing-page-screenshot.png",
    size: "412 KB",
    preview: null,
  },
  {
    id: "att_file_3",
    kind: "code",
    name: "export-remap.sql",
    size: "1.2 KB",
    preview: "ALTER VIEW billing_export RENAME COLUMN acct_ref TO account_reference;",
  },
  {
    id: "att_file_4",
    kind: "report",
    name: "june-usage-report.pdf",
    size: "204 KB",
    preview: "Monthly usage report — June 2026.",
  },
];

export const ATTACHABLE_WORKFLOWS: Attachment[] = [
  {
    id: "att_wf_1",
    kind: "workflow",
    name: "Weekly competitor brief",
    size: "Workflow",
    preview: "wfl_1 — gathers, summarises and files the weekly brief.",
  },
  {
    id: "att_wf_2",
    kind: "workflow",
    name: "Market signal digest",
    size: "Workflow",
    preview: "wfl_2 — the weekly market signals rollup.",
  },
];

export const ATTACHABLE_TASKS: Attachment[] = [
  {
    id: "att_tsk_1",
    kind: "task",
    name: "TASK-1001 — Weekly competitor brief",
    size: "Task",
    preview: "The brief's tracked run.",
  },
  {
    id: "att_tsk_2",
    kind: "task",
    name: "TASK-1004 — Dependency upgrade sweep",
    size: "Task",
    preview: "Two majors held back pending review.",
  },
];

export const ATTACHABLE_MEMORIES: Attachment[] = [
  {
    id: "att_mem_1",
    kind: "memory",
    name: "Competitor A moved to per-seat pricing",
    size: "Memory",
    preview: "mem_1 — the pricing move and the plan mix behind it.",
  },
  {
    id: "att_mem_2",
    kind: "memory",
    name: "House voice: sentence case, never title case",
    size: "Memory",
    preview: "mem_4 — the writing rules every draft follows.",
  },
];
