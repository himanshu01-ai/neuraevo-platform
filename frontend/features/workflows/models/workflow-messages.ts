import { WorkflowError } from "@/services/workflows";

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
