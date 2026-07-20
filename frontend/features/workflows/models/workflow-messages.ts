import { WorkflowError, type WorkflowRun, type WorkflowRunDetail } from "@/services/workflows";

/**
 * Just enough of a run to describe how it went.
 *
 * A live result and a recorded one differ in what they carry — one has an
 * identity and timings, the other does not — but they agree exactly on the
 * outcome, which is all these sentences are about. Naming that overlap lets one
 * wording serve both rather than each getting its own.
 */
type RunOutcome = Pick<
  WorkflowRun | WorkflowRunDetail,
  "status" | "completedStepCount" | "totalStepCount" | "error"
> & { failedStepId: string | null };

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
 * How a finished run reads in one line.
 *
 * The step tally is the honest summary of both outcomes: a completed run did all
 * of them, a failed run says how far it got before stopping. A run with no steps
 * can't happen — the platform refuses an empty workflow before running it — but
 * the wording holds if it ever did.
 */
export function workflowRunSummary(run: RunOutcome): string {
  const { completedStepCount: done, totalStepCount: total } = run;
  const steps = `${done} of ${total} step${total === 1 ? "" : "s"}`;

  if (run.status === "COMPLETED") return `Finished — ${steps} completed.`;
  if (run.status === "FAILED") return `Stopped — ${steps} completed.`;
  // PENDING or RUNNING: the platform answered before the run reached an end.
  return `Still running — ${steps} completed so far.`;
}

/**
 * Why a run stopped.
 *
 * The platform's own reason is shown when there is one — it names the capability
 * or the input that gave out, which nothing here could reconstruct. Its
 * "step failed: <id>" is the exception: that is an internal restatement of the
 * step we already name in the results, so it's replaced rather than repeated.
 */
export function workflowRunError(run: RunOutcome): string | null {
  if (run.status !== "FAILED") return null;
  const reason = run.error?.trim();
  if (!reason || /^step failed:/i.test(reason)) {
    return "A step didn't finish. The step that stopped the run is marked below.";
  }
  return reason;
}

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

/**
 * The same mapping, for something that went wrong with a *run* rather than a
 * workflow.
 *
 * Only one code needs different words. The adapter has one `not_found`, so a
 * missing run would otherwise be reported as a missing workflow — true only by
 * accident, and misleading when the workflow is sitting on the screen behind
 * the message.
 */
export function workflowRunErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof WorkflowError && error.code === "not_found") {
    return "That run is no longer available.";
  }
  return workflowErrorMessage(error, fallback);
}
