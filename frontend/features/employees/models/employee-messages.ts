import { EmployeeError } from "@/services/employees";

/**
 * What the employee screens say when an action finishes.
 *
 * One module so the directory, the profile and the builder never word the same
 * outcome three different ways. Messages are a sentence, past tense, and name
 * the employee — enough to confirm what happened without narrating it.
 */

export const employeeSaved = (name: string, isNew: boolean): string =>
  isNew ? `${name} was created.` : `${name} was saved.`;

export const employeeDuplicated = (name: string): string => `${name} was duplicated.`;

export const employeeArchived = (name: string): string => `${name} was archived.`;

export const employeeRestored = (name: string): string => `${name} was restored.`;

export const employeeDeleted = (name: string): string => `${name} was deleted.`;

/**
 * A failure in words a user can act on.
 *
 * The adapter already sorts transport failures into `EmployeeError` codes, so
 * the mapping happens once, here, against that vocabulary. Only `invalid_draft`
 * passes the server's own text through — it is the one case where the server
 * knows something specific about the request that we don't, and its message is
 * written for a person. Every other code gets our copy, so a 500's internals
 * can never reach the screen.
 */
export function employeeErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof EmployeeError)) return fallback;

  switch (error.code) {
    case "not_found":
      return "That employee no longer exists. It may have been deleted.";
    case "unavailable":
      return "The server can't be reached right now. Try again in a moment.";
    case "invalid_draft":
      return error.message;
    case "unknown":
      return fallback;
  }
}
