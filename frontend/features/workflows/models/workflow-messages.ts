import { WorkflowError } from "@/services/workflows";

/**
 * What the workflow screens say when a lifecycle action succeeds. Short, past
 * tense, and naming the workflow — the same shape as the employee domain's
 * success copy, so the two feel like one product.
 */
export const workflowPublished = (name: string): string => `${name} was published.`;
export const workflowUnpublished = (name: string): string => `${name} was moved back to draft.`;
export const workflowArchived = (name: string): string => `${name} was archived.`;
export const workflowRestored = (name: string): string => `${name} was restored.`;
export const workflowDuplicated = (name: string): string => `${name} was duplicated.`;
export const workflowDeleted = (name: string): string => `${name} was deleted.`;

/**
 * What the workflow screens say when an action fails.
 *
 * One module so the directory, the builder and the toolbar never word the same
 * outcome three different ways — the employee domain's `employeeErrorMessage`
 * in the same position.
 *
 * The adapter already sorts transport failures into `WorkflowError` codes, so
 * the mapping happens once, here, against that vocabulary. Only
 * `invalid_import` passes the server's own text through — it is the one case
 * where the server knows something specific about the request that we don't
 * (a rejected name, a malformed graph, an illegal lifecycle move), and its
 * message is written for a person. Every other code gets our copy, so a 500's
 * internals can never reach the screen.
 */
export function workflowErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof WorkflowError)) return fallback;

  switch (error.code) {
    case "not_found":
      return "That workflow no longer exists. It may have been deleted.";
    case "unavailable":
      return "The server can't be reached right now. Try again in a moment.";
    case "invalid_import":
      return error.message;
    case "unknown":
      return fallback;
  }
}
