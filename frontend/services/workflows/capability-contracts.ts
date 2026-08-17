/**
 * Canonical capability contracts — the builder's copy (Sprint 18.8).
 *
 * The platform owns these: `backend/app/services/runtime/capability_contracts.py`
 * is where they are defined, because the capabilities are what actually read
 * these inputs. This file mirrors that table so the builder can render a form,
 * validate it, and seed its defaults without asking the server mid-edit.
 *
 * The two are held together by a test, not by discipline:
 * `backend/tests/test_capability_contracts.py` loads this module and fails if a
 * single key, label, default or requirement differs. So this is a mirror that
 * cannot drift silently — which is the whole point, since a builder writing
 * `script` where the platform reads `python_code` is precisely the bug this
 * sprint exists to end.
 *
 * Deliberately dependency-free. No imports, no framework types: the parity test
 * loads it in a bare Node process, and anything it imported would have to load
 * there too.
 */

export type CapabilityValueType = "text" | "long_text" | "text_list" | "choice";

/** The input every operation-driven capability switches on. */
export const OPERATION_KEY = "operation";

/** `requiredFor` marker meaning "whichever action is chosen". */
export const ANY_OPERATION = "*";

export interface CapabilityInputContract {
  /** The name the platform reads, and therefore the name the builder stores. */
  key: string;
  /** How the input is named to a person. Keys never reach the screen. */
  label: string;
  valueType: CapabilityValueType;
  /** Allowed values for a `choice` input; empty otherwise. */
  choices: readonly string[];
  /** What the builder pre-fills when a step is added. */
  default: string | null;
  /** Actions that require this input. `["*"]` means always; empty means never. */
  requiredFor: readonly string[];
  helpText: string;
  placeholder: string;
}

export interface CapabilityContract {
  /** The builder's word for the step. */
  nodeKind: string;
  /** The platform's word for what runs it. Differs only for `file`. */
  capability: string;
  summary: string;
  inputs: readonly CapabilityInputContract[];
}

const input = (
  key: string,
  label: string,
  overrides: Partial<Omit<CapabilityInputContract, "key" | "label">> = {},
): CapabilityInputContract => ({
  key,
  label,
  valueType: "text",
  choices: [],
  default: null,
  requiredFor: [],
  helpText: "",
  placeholder: "",
  ...overrides,
});

export const CAPABILITY_CONTRACTS: readonly CapabilityContract[] = [
  {
    nodeKind: "browser",
    capability: "browser",
    summary: "Load one web page and return its content.",
    inputs: [
      input("target_url", "Page address", {
        requiredFor: [ANY_OPERATION],
        placeholder: "https://example.com",
        helpText: "The full address of the page to load.",
      }),
      input("session_id", "Session", {
        helpText: "Leave empty to use a fresh browser session for this step.",
      }),
    ],
  },
  {
    nodeKind: "python",
    capability: "python",
    summary: "Run Python and return what it produced.",
    inputs: [
      input("python_code", "Python code", {
        valueType: "long_text",
        requiredFor: [ANY_OPERATION],
        placeholder: "result = 1 + 1",
        helpText: "Assign to `result` to pass a value to the next step.",
      }),
    ],
  },
  {
    nodeKind: "file",
    capability: "filesystem",
    summary: "Read, write or list files in the workspace.",
    inputs: [
      input(OPERATION_KEY, "Action", {
        valueType: "choice",
        choices: ["READ", "WRITE", "APPEND", "LIST_DIRECTORY", "DELETE", "EXISTS"],
        default: "WRITE",
        requiredFor: [ANY_OPERATION],
      }),
      input("path", "File path", {
        requiredFor: ["READ", "WRITE", "APPEND", "DELETE", "EXISTS"],
        placeholder: "reports/summary.txt",
        helpText: "Relative to the workspace. Leave empty when listing its root.",
      }),
      input("content", "Contents", {
        valueType: "long_text",
        helpText: "What to write. An empty value creates an empty file.",
      }),
    ],
  },
  {
    nodeKind: "email",
    capability: "email",
    summary: "Send mail, or read what has arrived.",
    inputs: [
      input(OPERATION_KEY, "Action", {
        valueType: "choice",
        choices: ["SEND", "DRAFT", "READ_FOLDER", "LIST_FOLDERS"],
        default: "SEND",
        requiredFor: [ANY_OPERATION],
      }),
      input("to", "Recipients", {
        valueType: "text_list",
        requiredFor: ["SEND", "DRAFT"],
        placeholder: "someone@example.com",
        helpText: "One address per line.",
      }),
      input("subject", "Subject"),
      input("body_text", "Message", { valueType: "long_text" }),
      input("folder", "Folder", {
        placeholder: "INBOX",
        helpText: "Which folder to read. Defaults to the inbox.",
      }),
    ],
  },
  {
    nodeKind: "calendar",
    capability: "calendar",
    summary: "Create an event, or look at what is scheduled.",
    inputs: [
      input(OPERATION_KEY, "Action", {
        valueType: "choice",
        choices: ["CREATE", "LIST", "SEARCH"],
        default: "CREATE",
        requiredFor: [ANY_OPERATION],
      }),
      input("summary", "Title", { requiredFor: ["CREATE"] }),
      input("start_time", "Starts", {
        requiredFor: ["CREATE"],
        placeholder: "2026-08-01T09:00:00",
        helpText: "Date and time, as year-month-day followed by T and the time.",
      }),
      input("end_time", "Ends", {
        requiredFor: ["CREATE"],
        placeholder: "2026-08-01T09:30:00",
      }),
      input("location", "Location"),
      input("query", "Search for", { requiredFor: ["SEARCH"] }),
      input("time_zone", "Time zone", { default: "UTC" }),
    ],
  },
  {
    nodeKind: "github",
    capability: "github",
    summary: "Start a repository, or copy an existing one.",
    inputs: [
      input(OPERATION_KEY, "Action", {
        valueType: "choice",
        choices: ["INIT", "CLONE"],
        default: "INIT",
        requiredFor: [ANY_OPERATION],
      }),
      input("repository_name", "Repository name", { placeholder: "my-project" }),
      input("source_url", "Repository to copy", {
        requiredFor: ["CLONE"],
        placeholder: "https://github.com/owner/repo.git",
      }),
    ],
  },
];

const BY_NODE_KIND = new Map(CAPABILITY_CONTRACTS.map((c) => [c.nodeKind, c]));

/** The contract for a node kind, or `undefined` if the kind can't be executed. */
export function capabilityContract(nodeKind: string): CapabilityContract | undefined {
  return BY_NODE_KIND.get(nodeKind);
}

/** Whether a node kind is one the platform can run. */
export function isExecutableKind(nodeKind: string): boolean {
  return BY_NODE_KIND.has(nodeKind);
}

/**
 * Whether an input is needed given the action a step is set to.
 *
 * The action decides the rest: a File step writing needs a path, the same step
 * listing a directory does not.
 */
export function isInputRequired(
  spec: CapabilityInputContract,
  operation: string | undefined,
): boolean {
  if (spec.requiredFor.includes(ANY_OPERATION)) return true;
  return operation !== undefined && spec.requiredFor.includes(operation);
}

/**
 * What a newly added step of this kind starts out configured with.
 *
 * Only the contract's declared defaults, so a step is born with its action
 * already chosen rather than in a state the author has to notice and fix. The
 * platform would fall back to the same values on its own; writing them down
 * means the saved workflow says what it does.
 */
export function defaultConfig(nodeKind: string): Record<string, string> {
  const contract = BY_NODE_KIND.get(nodeKind);
  if (!contract) return {};

  const config: Record<string, string> = {};
  for (const spec of contract.inputs) {
    if (spec.default !== null) config[spec.key] = spec.default;
  }
  return config;
}
