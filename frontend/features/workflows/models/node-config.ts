/**
 * Reading and writing a step's configured values (Sprint 18.8).
 *
 * A config value is either text or a list of text, because that is what the
 * capability contracts declare. Two places need to agree on how those are read:
 * the inspector that edits them and the validation that judges them. This is
 * that agreement, so neither has to guess what an empty list looks like.
 *
 * Nothing here knows what a value *means*. It knows what shape it is in.
 */

import {
  ANY_OPERATION,
  type NodeConfigValue,
  type WorkflowNode,
} from "@/services/workflows";
import type { NodeConfigField } from "./node-types";

/** A config value as text. A list is not text, so it reads as empty. */
export function readTextValue(value: NodeConfigValue | undefined): string {
  return typeof value === "string" ? value : "";
}

/** A config value as a list. Text is not a list, so it reads as empty. */
export function readListValue(value: NodeConfigValue | undefined): string[] {
  return Array.isArray(value) ? value : [];
}

/**
 * A list field's text box → the list it stands for.
 *
 * One value per line, with blanks dropped: a trailing newline while typing is
 * not an empty recipient, and the platform would reject it as one.
 */
export function toListValue(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

/** Whether a field has been filled in, whichever shape it takes. */
export function hasValue(value: NodeConfigValue | undefined): boolean {
  if (Array.isArray(value)) return value.some((item) => item.trim().length > 0);
  return typeof value === "string" && value.trim().length > 0;
}

/**
 * Whether a field is required given the action the step is set to.
 *
 * A field with no `requiredFor` belongs to one of the authoring-only kinds,
 * which nothing runs and so nothing requires.
 */
export function isFieldRequired(field: NodeConfigField, operation: string): boolean {
  if (!field.requiredFor) return false;
  if (field.requiredFor.includes(ANY_OPERATION)) return true;
  return operation !== "" && field.requiredFor.includes(operation);
}

/** Every required field on this step that hasn't been filled in. */
export function missingRequiredFields(
  node: WorkflowNode,
  fields: readonly NodeConfigField[],
): NodeConfigField[] {
  const operation = readTextValue(node.config.operation);
  return fields.filter(
    (field) => isFieldRequired(field, operation) && !hasValue(node.config[field.key]),
  );
}
