import { NODE_KINDS, type NodeKind } from "@/services/workflows";

/**
 * The drag-and-drop contract between the step library and the canvas. A custom
 * MIME type keeps the canvas from accepting arbitrary dragged text.
 */
export const STEP_DRAG_TYPE = "application/x-neuraevo-step";

/** Narrows a dataTransfer payload — anything can be dropped on a drop target. */
export function isNodeKind(value: string): value is NodeKind {
  return (NODE_KINDS as readonly string[]).includes(value);
}
