"""Canonical capability contracts (Sprint 18.8 — one contract, three consumers).

The single definition of what each executable workflow step *is*: which builder
node kind it comes from, which runtime capability runs it, and exactly which
inputs that capability needs. Three places read it and none of them restates it:

* **Translation** (:mod:`app.services.workflow_translation`) maps a node kind to
  a capability name through :data:`NODE_KIND_TO_CAPABILITY`.
* **Execution** (:class:`app.services.workflow_execution_service.WorkflowExecutionService`)
  checks a translated step's inputs with :func:`validate_inputs` before the
  runtime is asked to run anything.
* **Authoring** — the builder's ``services/workflows/capability-contracts.ts``
  mirrors this table so the inspector emits these keys directly, and
  ``tests/test_capability_contracts.py`` fails if the two ever disagree.

Before this sprint the builder wrote its own key names (``script``, ``repository``,
``query``) while the capabilities read theirs (``python_code``,
``repository_name``, ``target_url``), so every workflow authored in the UI
translated cleanly and then failed on its first step. This module ends that by
giving both sides one vocabulary rather than a converter between two.

What it is not: it does not execute, does not repair a configuration, and does
not restate a capability's own semantics. Each capability remains the authority
on what it does with an input — this records only which inputs it needs to be
given, which is the part the author has to get right.

Scope note. A contract covers the operations a *single, self-contained* step can
perform. Operations that only make sense against state an earlier step produced
(GitHub's ``COMMIT``, which needs a repository id from an ``INIT``) are left out:
the builder cannot yet wire one step's output into another's input, so offering
them would be offering a step that cannot succeed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

# The input every operation-driven capability switches on. Named once here so
# neither this module nor its readers spell it inline.
OPERATION_KEY = "operation"

# Marks an input as required no matter which operation was chosen — either the
# capability has no operation switch at all (browser, python) or the input is
# needed by every operation it does have.
ANY_OPERATION = "*"


class ValueType(str, Enum):
    """How an input is written, which decides the control that collects it.

    ``TEXT`` is a single line and ``LONG_TEXT`` a multi-line body; both arrive as
    a string. ``CHOICE`` is one of a fixed set. ``TEXT_LIST`` is the one that
    matters: the capabilities that take several addresses want a real list, and a
    single string is rejected — so the builder must produce a list, not something
    translation later splits apart.
    """

    TEXT = "text"
    LONG_TEXT = "long_text"
    TEXT_LIST = "text_list"
    CHOICE = "choice"


@dataclass(frozen=True)
class CapabilityInput:
    """One input a capability reads, and when it has to be there.

    ``key`` is the name the capability reads and therefore the name the builder
    stores. ``label`` is how it is named to a person — in the inspector and in
    any validation message, so no key ever reaches the screen.

    ``required_for`` lists the operations that need it: empty means optional, and
    ``(ANY_OPERATION,)`` means always. ``default`` is what the builder pre-fills
    when a step is added, so an authored document says what it means rather than
    relying on a fallback happening to match.
    """

    key: str
    label: str
    value_type: ValueType = ValueType.TEXT
    choices: Tuple[str, ...] = ()
    default: Optional[str] = None
    required_for: Tuple[str, ...] = ()
    help_text: str = ""
    placeholder: str = ""

    def is_required_for(self, operation: str) -> bool:
        """Whether this input must be present for ``operation``."""
        if ANY_OPERATION in self.required_for:
            return True
        return operation in self.required_for


@dataclass(frozen=True)
class CapabilityContract:
    """What one executable node kind needs to run.

    ``node_kind`` is the builder's word for the step, ``capability`` the
    runtime's for the thing that runs it. They differ in one case — the builder's
    ``file`` is the runtime's ``filesystem`` — and this is the only place that
    difference is recorded.
    """

    node_kind: str
    capability: str
    summary: str = ""
    inputs: Tuple[CapabilityInput, ...] = field(default_factory=tuple)

    @property
    def operation_input(self) -> Optional[CapabilityInput]:
        """The operation switch, or ``None`` for a capability that has one job."""
        for spec in self.inputs:
            if spec.key == OPERATION_KEY:
                return spec
        return None

    def input_for(self, key: str) -> Optional[CapabilityInput]:
        for spec in self.inputs:
            if spec.key == key:
                return spec
        return None


# =====================================================================
# The contracts
# =====================================================================
#
# Every required/optional split below was established by running the capability,
# not by reading it: an input is marked required only where the capability
# actually refuses without it.

_BROWSER = CapabilityContract(
    node_kind="browser",
    capability="browser",
    summary="Load one web page and return its content.",
    inputs=(
        CapabilityInput(
            key="target_url",
            label="Page address",
            required_for=(ANY_OPERATION,),
            placeholder="https://example.com",
            help_text="The full address of the page to load.",
        ),
        CapabilityInput(
            key="session_id",
            label="Session",
            help_text="Leave empty to use a fresh browser session for this step.",
        ),
    ),
)

_PYTHON = CapabilityContract(
    node_kind="python",
    capability="python",
    summary="Run Python and return what it produced.",
    inputs=(
        CapabilityInput(
            key="python_code",
            label="Python code",
            value_type=ValueType.LONG_TEXT,
            required_for=(ANY_OPERATION,),
            placeholder="result = 1 + 1",
            help_text="Assign to `result` to pass a value to the next step.",
        ),
    ),
)

_FILESYSTEM = CapabilityContract(
    node_kind="file",
    capability="filesystem",
    summary="Read, write or list files in the workspace.",
    inputs=(
        CapabilityInput(
            key=OPERATION_KEY,
            label="Action",
            value_type=ValueType.CHOICE,
            choices=("READ", "WRITE", "APPEND", "LIST_DIRECTORY", "DELETE", "EXISTS"),
            default="WRITE",
            required_for=(ANY_OPERATION,),
        ),
        CapabilityInput(
            key="path",
            label="File path",
            required_for=("READ", "WRITE", "APPEND", "DELETE", "EXISTS"),
            placeholder="reports/summary.txt",
            help_text="Relative to the workspace. Leave empty when listing its root.",
        ),
        CapabilityInput(
            key="content",
            label="Contents",
            value_type=ValueType.LONG_TEXT,
            help_text="What to write. An empty value creates an empty file.",
        ),
    ),
)

_EMAIL = CapabilityContract(
    node_kind="email",
    capability="email",
    summary="Send mail, or read what has arrived.",
    inputs=(
        CapabilityInput(
            key=OPERATION_KEY,
            label="Action",
            value_type=ValueType.CHOICE,
            choices=("SEND", "DRAFT", "READ_FOLDER", "LIST_FOLDERS"),
            default="SEND",
            required_for=(ANY_OPERATION,),
        ),
        CapabilityInput(
            key="to",
            label="Recipients",
            value_type=ValueType.TEXT_LIST,
            required_for=("SEND", "DRAFT"),
            placeholder="someone@example.com",
            help_text="One address per line.",
        ),
        CapabilityInput(key="subject", label="Subject"),
        CapabilityInput(key="body_text", label="Message", value_type=ValueType.LONG_TEXT),
        CapabilityInput(
            key="folder",
            label="Folder",
            placeholder="INBOX",
            help_text="Which folder to read. Defaults to the inbox.",
        ),
    ),
)

_CALENDAR = CapabilityContract(
    node_kind="calendar",
    capability="calendar",
    summary="Create an event, or look at what is scheduled.",
    inputs=(
        CapabilityInput(
            key=OPERATION_KEY,
            label="Action",
            value_type=ValueType.CHOICE,
            choices=("CREATE", "LIST", "SEARCH"),
            default="CREATE",
            required_for=(ANY_OPERATION,),
        ),
        CapabilityInput(key="summary", label="Title", required_for=("CREATE",)),
        CapabilityInput(
            key="start_time",
            label="Starts",
            required_for=("CREATE",),
            placeholder="2026-08-01T09:00:00",
            help_text="Date and time, as year-month-day followed by T and the time.",
        ),
        CapabilityInput(
            key="end_time",
            label="Ends",
            required_for=("CREATE",),
            placeholder="2026-08-01T09:30:00",
        ),
        CapabilityInput(key="location", label="Location"),
        CapabilityInput(key="query", label="Search for", required_for=("SEARCH",)),
        CapabilityInput(key="time_zone", label="Time zone", default="UTC"),
    ),
)

_GITHUB = CapabilityContract(
    node_kind="github",
    capability="github",
    summary="Start a repository, or copy an existing one.",
    inputs=(
        CapabilityInput(
            key=OPERATION_KEY,
            label="Action",
            value_type=ValueType.CHOICE,
            choices=("INIT", "CLONE"),
            default="INIT",
            required_for=(ANY_OPERATION,),
        ),
        CapabilityInput(
            key="repository_name",
            label="Repository name",
            placeholder="my-project",
        ),
        CapabilityInput(
            key="source_url",
            label="Repository to copy",
            required_for=("CLONE",),
            placeholder="https://github.com/owner/repo.git",
        ),
    ),
)

CONTRACTS: Tuple[CapabilityContract, ...] = (
    _BROWSER,
    _PYTHON,
    _FILESYSTEM,
    _EMAIL,
    _CALENDAR,
    _GITHUB,
)

CONTRACT_BY_NODE_KIND: Dict[str, CapabilityContract] = {
    contract.node_kind: contract for contract in CONTRACTS
}

CONTRACT_BY_CAPABILITY: Dict[str, CapabilityContract] = {
    contract.capability: contract for contract in CONTRACTS
}

# Authoring node kind → runtime capability. The one table translation needs, and
# the reason it no longer keeps a copy of its own.
NODE_KIND_TO_CAPABILITY: Dict[str, str] = {
    contract.node_kind: contract.capability for contract in CONTRACTS
}


# =====================================================================
# Validation
# =====================================================================


def _is_blank(value: Any, value_type: ValueType) -> bool:
    """Whether ``value`` counts as "not supplied" for its type.

    A list of empty strings is as absent as no list at all — a recipients box
    containing only blank lines has not been filled in.
    """
    if value is None:
        return True
    if value_type is ValueType.TEXT_LIST:
        if isinstance(value, str):
            # A string where a list belongs is not blank, but it is wrong; the
            # type check below reports that, and reporting "required" too would
            # be a second complaint about one mistake.
            return not value.strip()
        if not isinstance(value, (list, tuple)):
            return True
        return not [item for item in value if str(item).strip()]
    return not str(value).strip()


def validate_inputs(capability: str, inputs: Mapping[str, Any]) -> List[str]:
    """Check one step's inputs against its contract.

    Returns a message per problem, worded for the person who authored the step —
    field labels, never keys, and nothing about capabilities or dispatch. An
    empty list means the step has everything it needs; whether it then *succeeds*
    is the capability's business.

    A capability with no contract returns no messages: this module refuses to
    guess at requirements it has not recorded.
    """
    contract = CONTRACT_BY_CAPABILITY.get(capability)
    if contract is None:
        return []

    messages: List[str] = []
    operation_spec = contract.operation_input
    operation = str(inputs.get(OPERATION_KEY, "") or "").strip()

    # The operation decides which other inputs are needed, so an unusable one is
    # reported on its own — the rest of the check would be guesswork.
    if operation_spec is not None:
        if not operation:
            return [f"{operation_spec.label} is required."]
        if operation not in operation_spec.choices:
            allowed = ", ".join(operation_spec.choices)
            return [f"{operation_spec.label} must be one of: {allowed}."]

    for spec in contract.inputs:
        if spec.key == OPERATION_KEY:
            continue
        value = inputs.get(spec.key)

        if spec.is_required_for(operation) and _is_blank(value, spec.value_type):
            messages.append(f"{spec.label} is required.")
            continue

        if value is None or _is_blank(value, spec.value_type):
            continue

        if spec.value_type is ValueType.TEXT_LIST and not isinstance(value, (list, tuple)):
            messages.append(f"{spec.label} must be a list of values.")
        elif spec.value_type is ValueType.CHOICE and str(value) not in spec.choices:
            allowed = ", ".join(spec.choices)
            messages.append(f"{spec.label} must be one of: {allowed}.")

    return messages
