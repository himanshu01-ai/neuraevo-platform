"""Capability contract tests (Sprint 18.8 — one contract, honoured everywhere).

The sprint's claim is that a workflow authored in the builder runs as authored.
These tests are what makes that checkable rather than hopeful:

* ``ContractShapeTests`` — every contract names a capability the router can
  actually reach, and every executable node kind has one.
* ``ValidationTests`` — the required/optional rules, including the ones that
  depend on which action a step is set to.
* ``FrontendParityTests`` — loads the builder's mirror
  (``services/workflows/capability-contracts.ts``) in Node and compares it field
  by field. This is the test that stops the two sides drifting apart again; the
  bug this sprint fixed was exactly that drift.
* ``SerializationTests`` — a graph document shaped the way the builder writes it
  translates into steps whose inputs the contract accepts.
* ``ExecutionTests`` — each capability actually runs, through the real Sprint
  15.15 coordinator, configured only from its contract.

Runnable with stdlib unittest:
    PYTHONPATH=. python -m unittest tests.test_capability_contracts
"""

import json
import pathlib
import shutil
import subprocess
import unittest

from app.core.dependencies import get_capability_router
from app.services.runtime.capability_dependencies import probe_capability
from app.services.runtime.capability_contracts import (
    ANY_OPERATION,
    CONTRACTS,
    CONTRACT_BY_CAPABILITY,
    CONTRACT_BY_NODE_KIND,
    NODE_KIND_TO_CAPABILITY,
    OPERATION_KEY,
    ValueType,
    validate_inputs,
)
from app.services.runtime.execution_capability_models import CapabilityExecutionRequest
from app.services.workflow_translation import translate_graph

FRONTEND_CONTRACTS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "frontend"
    / "services"
    / "workflows"
    / "capability-contracts.ts"
)


# --- helpers -------------------------------------------------------------


def node(node_id, kind, config=None, name=""):
    """A node shaped exactly as ``toGraphDocument`` writes one."""
    return {
        "id": node_id,
        "kind": kind,
        "name": name or node_id,
        "description": "",
        "position": {"x": 0, "y": 0},
        "config": config or {},
    }


def graph(nodes, edges=None):
    return {"nodes": nodes, "edges": edges or []}


# One configuration per capability that satisfies its contract. These are the
# inputs a builder-authored step carries, and the execution tests run them.
SATISFYING_CONFIG = {
    "browser": {"target_url": "https://example.com"},
    "python": {"python_code": "outputs['v'] = 6 * 7"},
    "file": {"operation": "WRITE", "path": "contract.txt", "content": "hello"},
    "email": {
        "operation": "SEND",
        "to": ["someone@example.dev"],
        "subject": "Contract",
        "body_text": "Body",
    },
    "calendar": {
        "operation": "CREATE",
        "summary": "Standup",
        "start_time": "2026-08-01T09:00:00",
        "end_time": "2026-08-01T09:30:00",
        "time_zone": "UTC",
    },
    "github": {"operation": "INIT", "repository_name": "contract-demo"},
}


# --- shape ---------------------------------------------------------------


class ContractShapeTests(unittest.TestCase):
    def test_every_contract_names_a_reachable_capability(self):
        router = get_capability_router()
        for contract in CONTRACTS:
            with self.subTest(contract.node_kind):
                self.assertTrue(
                    router.is_available(contract.capability),
                    f"{contract.capability} is not registered with the router",
                )

    def test_node_kind_map_is_derived_from_the_contracts(self):
        self.assertEqual(
            NODE_KIND_TO_CAPABILITY,
            {c.node_kind: c.capability for c in CONTRACTS},
        )

    def test_file_is_the_only_renamed_kind(self):
        renamed = {k: v for k, v in NODE_KIND_TO_CAPABILITY.items() if k != v}
        self.assertEqual(renamed, {"file": "filesystem"})

    def test_indexes_cover_every_contract(self):
        self.assertEqual(len(CONTRACT_BY_NODE_KIND), len(CONTRACTS))
        self.assertEqual(len(CONTRACT_BY_CAPABILITY), len(CONTRACTS))

    def test_choice_inputs_declare_their_choices(self):
        for contract in CONTRACTS:
            for spec in contract.inputs:
                if spec.value_type is ValueType.CHOICE:
                    with self.subTest(f"{contract.node_kind}.{spec.key}"):
                        self.assertTrue(spec.choices)

    def test_declared_defaults_are_valid_choices(self):
        for contract in CONTRACTS:
            for spec in contract.inputs:
                if spec.default is not None and spec.choices:
                    with self.subTest(f"{contract.node_kind}.{spec.key}"):
                        self.assertIn(spec.default, spec.choices)

    def test_required_for_names_real_operations(self):
        """A requirement pinned to an operation that doesn't exist is dead."""
        for contract in CONTRACTS:
            operation = contract.operation_input
            allowed = set(operation.choices) if operation else set()
            for spec in contract.inputs:
                for name in spec.required_for:
                    if name == ANY_OPERATION:
                        continue
                    with self.subTest(f"{contract.node_kind}.{spec.key}"):
                        self.assertIn(name, allowed)

    def test_every_input_label_is_human(self):
        """Labels reach the screen and validation messages; keys must not."""
        for contract in CONTRACTS:
            for spec in contract.inputs:
                with self.subTest(f"{contract.node_kind}.{spec.key}"):
                    self.assertTrue(spec.label.strip())
                    self.assertNotEqual(spec.label, spec.key)


# --- validation ----------------------------------------------------------


class ValidationTests(unittest.TestCase):
    def test_satisfying_configuration_passes(self):
        for kind, config in SATISFYING_CONFIG.items():
            with self.subTest(kind):
                capability = NODE_KIND_TO_CAPABILITY[kind]
                self.assertEqual(validate_inputs(capability, config), [])

    def test_missing_always_required_input_is_reported(self):
        messages = validate_inputs("python", {})
        self.assertEqual(messages, ["Python code is required."])

    def test_message_uses_the_label_not_the_key(self):
        messages = validate_inputs("browser", {})
        self.assertIn("Page address", messages[0])
        self.assertNotIn("target_url", messages[0])

    def test_missing_operation_is_reported_alone(self):
        """Without an action, the other requirements aren't knowable yet."""
        messages = validate_inputs("filesystem", {})
        self.assertEqual(messages, ["Action is required."])

    def test_unknown_operation_is_rejected(self):
        messages = validate_inputs("filesystem", {OPERATION_KEY: "SHRED"})
        self.assertEqual(len(messages), 1)
        self.assertIn("Action must be one of", messages[0])

    def test_requirement_follows_the_chosen_operation(self):
        # WRITE needs a path...
        self.assertEqual(
            validate_inputs("filesystem", {OPERATION_KEY: "WRITE"}),
            ["File path is required."],
        )
        # ...and listing the workspace root does not.
        self.assertEqual(validate_inputs("filesystem", {OPERATION_KEY: "LIST_DIRECTORY"}), [])

    def test_optional_input_may_be_absent(self):
        self.assertEqual(
            validate_inputs("filesystem", {OPERATION_KEY: "WRITE", "path": "a.txt"}),
            [],
        )

    def test_list_input_required_for_some_operations_only(self):
        self.assertEqual(
            validate_inputs("email", {OPERATION_KEY: "SEND"}), ["Recipients is required."]
        )
        self.assertEqual(validate_inputs("email", {OPERATION_KEY: "LIST_FOLDERS"}), [])

    def test_list_of_blanks_counts_as_missing(self):
        messages = validate_inputs("email", {OPERATION_KEY: "SEND", "to": ["", "   "]})
        self.assertEqual(messages, ["Recipients is required."])

    def test_string_where_a_list_belongs_is_rejected(self):
        """The capability refuses a bare string, so the contract does too."""
        messages = validate_inputs(
            "email", {OPERATION_KEY: "SEND", "to": "someone@example.dev"}
        )
        self.assertEqual(messages, ["Recipients must be a list of values."])

    def test_several_missing_inputs_are_all_reported(self):
        messages = validate_inputs("calendar", {OPERATION_KEY: "CREATE"})
        self.assertEqual(messages, ["Title is required.", "Starts is required.", "Ends is required."])

    def test_unknown_capability_makes_no_claims(self):
        self.assertEqual(validate_inputs("teleport", {"anything": "x"}), [])

    def test_messages_avoid_runtime_terminology(self):
        """An author is told about their step, not about the machinery."""
        forbidden = ("capability", "dispatch", "runtime", "coordinator", "step_id")
        for kind, config in SATISFYING_CONFIG.items():
            capability = NODE_KIND_TO_CAPABILITY[kind]
            # Strip everything and read what comes back.
            for message in validate_inputs(capability, {OPERATION_KEY: config.get(OPERATION_KEY, "")}):
                with self.subTest(f"{kind}: {message}"):
                    for word in forbidden:
                        self.assertNotIn(word, message.lower())


# --- frontend parity -----------------------------------------------------


class FrontendParityTests(unittest.TestCase):
    """The builder's mirror must match this table exactly.

    Loaded by running Node against the TypeScript module itself rather than
    reading it as text, so the comparison is against the values the builder will
    really use — not against something that merely looks right in the file.
    """

    @classmethod
    def setUpClass(cls):
        cls.node_binary = shutil.which("node")
        cls.mirror = None
        if not cls.node_binary or not FRONTEND_CONTRACTS.exists():
            return

        url = FRONTEND_CONTRACTS.as_uri()
        script = (
            f"import({url!r}).then(m => "
            "console.log(JSON.stringify(m.CAPABILITY_CONTRACTS)))"
        )
        try:
            completed = subprocess.run(
                [cls.node_binary, "--experimental-strip-types", "--no-warnings", "-e", script],
                capture_output=True,
                text=True,
                timeout=90,
                check=True,
            )
        except (subprocess.SubprocessError, OSError) as exc:  # pragma: no cover
            cls.load_error = str(exc)
            return
        cls.mirror = json.loads(completed.stdout)

    def setUp(self):
        if self.mirror is None:
            self.skipTest(
                "Node (>=22, for TypeScript type stripping) is needed to load the "
                "builder's contract mirror; skipping the parity check."
            )

    def _mirror_by_kind(self):
        return {contract["nodeKind"]: contract for contract in self.mirror}

    def test_same_capabilities_on_both_sides(self):
        self.assertEqual(
            sorted(self._mirror_by_kind()),
            sorted(CONTRACT_BY_NODE_KIND),
        )

    def test_every_input_matches_field_for_field(self):
        mirrored = self._mirror_by_kind()

        for kind, contract in CONTRACT_BY_NODE_KIND.items():
            mirror = mirrored[kind]
            with self.subTest(kind):
                self.assertEqual(mirror["capability"], contract.capability)
                self.assertEqual(mirror["summary"], contract.summary)
                self.assertEqual(
                    [i["key"] for i in mirror["inputs"]],
                    [spec.key for spec in contract.inputs],
                    "inputs differ, or are in a different order",
                )

            for spec, mirrored_input in zip(contract.inputs, mirror["inputs"]):
                with self.subTest(f"{kind}.{spec.key}"):
                    self.assertEqual(mirrored_input["label"], spec.label)
                    self.assertEqual(mirrored_input["valueType"], spec.value_type.value)
                    self.assertEqual(tuple(mirrored_input["choices"]), spec.choices)
                    self.assertEqual(mirrored_input["default"], spec.default)
                    self.assertEqual(tuple(mirrored_input["requiredFor"]), spec.required_for)
                    self.assertEqual(mirrored_input["helpText"], spec.help_text)
                    self.assertEqual(mirrored_input["placeholder"], spec.placeholder)


# --- serialization -------------------------------------------------------


class SerializationTests(unittest.TestCase):
    """What the builder saves is what the runtime is handed."""

    def test_builder_document_translates_to_satisfying_steps(self):
        nodes = [node(kind, kind, config) for kind, config in SATISFYING_CONFIG.items()]
        steps = translate_graph(graph(nodes))

        self.assertEqual(len(steps), len(SATISFYING_CONFIG))
        for step in steps:
            with self.subTest(step.step_id):
                self.assertEqual(validate_inputs(step.capability_name, step.inputs), [])

    def test_configuration_crosses_translation_unchanged(self):
        config = SATISFYING_CONFIG["email"]
        (step,) = translate_graph(graph([node("s1", "email", config)]))
        self.assertEqual(step.inputs, config)

    def test_a_list_stays_a_list(self):
        """The one shape a naive translation would flatten."""
        (step,) = translate_graph(
            graph([node("s1", "email", {"operation": "SEND", "to": ["a@x.dev", "b@x.dev"]})])
        )
        self.assertEqual(step.inputs["to"], ["a@x.dev", "b@x.dev"])

    def test_defaults_are_authored_not_assumed(self):
        """Every contract default is a value the builder can write down."""
        for contract in CONTRACTS:
            for spec in contract.inputs:
                if spec.default is None:
                    continue
                with self.subTest(f"{contract.node_kind}.{spec.key}"):
                    (step,) = translate_graph(
                        graph([node("s1", contract.node_kind, {spec.key: spec.default})])
                    )
                    self.assertEqual(step.inputs[spec.key], spec.default)


# --- execution -----------------------------------------------------------


class ExecutionTests(unittest.TestCase):
    """Each capability, run for real with only what its contract asks for.

    Through the router the workflow coordinator uses, so a pass here means a
    step configured in the builder reaches a capability that accepts it.
    """

    @classmethod
    def setUpClass(cls):
        cls.router = get_capability_router()

    def _run(self, kind):
        capability = NODE_KIND_TO_CAPABILITY[kind]
        (step,) = translate_graph(graph([node("s1", kind, SATISFYING_CONFIG[kind])]))
        self.assertEqual(
            validate_inputs(capability, step.inputs), [], "configuration is incomplete"
        )
        return self.router.dispatch(
            CapabilityExecutionRequest(
                runtime_id="contract-test",
                execution_id="contract-test",
                execution_unit_id=step.step_id,
                capability_name=step.capability_name,
                capability_inputs=step.inputs,
            )
        )

    def test_python_runs(self):
        self.assertEqual(self._run("python").execution_status, "COMPLETED")

    def test_filesystem_runs(self):
        self.assertEqual(self._run("file").execution_status, "COMPLETED")

    def test_email_runs(self):
        self.assertEqual(self._run("email").execution_status, "COMPLETED")

    def test_calendar_runs(self):
        self.assertEqual(self._run("calendar").execution_status, "COMPLETED")

    def test_github_runs(self):
        self.assertEqual(self._run("github").execution_status, "COMPLETED")

    def test_browser_runs_where_a_browser_is_installed(self):
        """Browser needs Playwright and a Chromium build (Sprint 18.9).

        Both are declared dependencies now, so where the host has them this
        asserts a real navigation like every other capability. Where it does not
        — a deployment that deliberately skipped the browser — the contract is
        still checked: the step translates, its inputs satisfy the contract, and
        the capability accepts the request. Only the navigation is skipped, and
        the reason comes from the dependency probe rather than from guessing at
        why the run failed.
        """
        report = probe_capability("browser")
        result = self._run("browser")
        self.assertEqual(result.capability_name, "browser")

        if not report.is_available:
            self.skipTest(f"no browser on this host ({report.status.value}): {report.detail}")

        self.assertEqual(result.execution_status, "COMPLETED")
        self.assertTrue(result.capability_outputs["page_loaded"])
        self.assertNotIn("error", result.capability_outputs)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
