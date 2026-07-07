"""Unit tests for the Sprint 14.3 Execution Capability Interface.

Covers the provider-independent execution-capability contract end to end without
touching any network, SDK, AI, dispatcher, concrete capability, or database:

* the immutable :class:`CapabilityExecutionRequest` / :class:`CapabilityExecution
  Result` DTOs and the :class:`CapabilityExecutionStatus` enum (defaults,
  immutability, required fields, enum values);
* the abstract :class:`ExecutionCapability` contract (abstract enforcement,
  contract shape, provider independence, statelessness, determinism) exercised
  through a minimal in-test capability double (never a real capability);
* the composition-root seam (``get_execution_capability`` raising
  ``NotImplementedError`` like the project's other provider seams, plus
  ``ExecutionCapabilityDep``); and
* regression that the Sprint 14.1/14.2 runtime and the Sprint 11 seams are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_capability
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)


# =====================================================================
# Helpers / in-test doubles (NOT real capabilities)
# =====================================================================
def _request(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        execution_unit_id="unit-1",
        capability_name="SomeCapability",
        capability_inputs={},
        capability_metadata={},
    )
    data.update(overrides)
    return CapabilityExecutionRequest(**data)


def _result(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        execution_unit_id="unit-1",
        capability_name="SomeCapability",
        execution_status="COMPLETED",
        capability_outputs={},
        execution_metadata={},
    )
    data.update(overrides)
    return CapabilityExecutionResult(**data)


class _EchoCapability(ExecutionCapability):
    """Deterministic contract double: echoes inputs to outputs, no side effects.

    This is a *test double* used only to exercise the abstract contract — it is
    not a real capability, knows no Browser/Email/Calendar/etc., and performs no
    networking or SDK work.
    """

    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=CapabilityExecutionStatus.COMPLETED.value,
            capability_outputs=dict(request.capability_inputs),
            execution_metadata={},
        )


class _IncompleteCapability(ExecutionCapability):
    """A subclass that fails to implement ``execute`` — must stay abstract."""


# =====================================================================
# DTOs
# =====================================================================
class CapabilityModelTests(unittest.TestCase):
    def test_request_defaults(self):
        request = CapabilityExecutionRequest(
            runtime_id="r",
            execution_id="e",
            execution_unit_id="u",
            capability_name="c",
        )
        self.assertEqual(request.capability_inputs, {})
        self.assertEqual(request.capability_metadata, {})

    def test_result_defaults(self):
        result = CapabilityExecutionResult(
            runtime_id="r",
            execution_id="e",
            execution_unit_id="u",
            capability_name="c",
            execution_status="READY",
        )
        self.assertEqual(result.capability_outputs, {})
        self.assertEqual(result.execution_metadata, {})

    def test_request_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            CapabilityExecutionRequest(runtime_id="r")  # rest missing

    def test_result_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            CapabilityExecutionResult(runtime_id="r")  # rest missing

    def test_request_immutable(self):
        with self.assertRaises(ValidationError):
            _request().capability_name = "Other"
        with self.assertRaises(ValidationError):
            _request().capability_inputs = {"x": 1}

    def test_result_immutable(self):
        with self.assertRaises(ValidationError):
            _result().execution_status = "FAILED"

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in CapabilityExecutionStatus},
            {"READY", "EXECUTING", "COMPLETED", "FAILED", "CANCELLED"},
        )


# =====================================================================
# Provider independence
# =====================================================================
class ProviderIndependenceTests(unittest.TestCase):
    def test_capability_name_is_free_form(self):
        # No enum constrains the capability name — any label is accepted, so the
        # contract knows nothing about concrete capabilities.
        for name in ("Browser", "Email", "TotallyMadeUpCapability", "x-9"):
            self.assertEqual(_request(capability_name=name).capability_name, name)

    def test_inputs_and_outputs_are_plain_data(self):
        request = _request(capability_inputs={"a": 1, "b": "two", "c": True})
        result = _EchoCapability().execute(request)
        plain = (str, int, float, bool, type(None))
        for value in list(request.capability_inputs.values()) + list(
            result.capability_outputs.values()
        ):
            self.assertIsInstance(value, plain)

    def test_interface_exposes_only_execute(self):
        # The contract's only abstract method is ``execute``.
        self.assertEqual(
            set(ExecutionCapability.__abstractmethods__), {"execute"}
        )


# =====================================================================
# Interface contract
# =====================================================================
class InterfaceContractTests(unittest.TestCase):
    def test_execute_returns_result(self):
        result = _EchoCapability().execute(_request())
        self.assertIsInstance(result, CapabilityExecutionResult)

    def test_execute_preserves_linkage(self):
        request = _request(
            runtime_id="runtime-abc",
            execution_id="exec-abc",
            execution_unit_id="unit-7",
            capability_name="Echo",
        )
        result = _EchoCapability().execute(request)
        self.assertEqual(result.runtime_id, request.runtime_id)
        self.assertEqual(result.execution_id, request.execution_id)
        self.assertEqual(result.execution_unit_id, request.execution_unit_id)
        self.assertEqual(result.capability_name, request.capability_name)

    def test_result_carries_status_and_outputs(self):
        result = _EchoCapability().execute(_request(capability_inputs={"k": 1}))
        self.assertEqual(result.execution_status, "COMPLETED")
        self.assertEqual(result.capability_outputs, {"k": 1})


# =====================================================================
# Abstract enforcement
# =====================================================================
class AbstractEnforcementTests(unittest.TestCase):
    def test_interface_is_abstract(self):
        with self.assertRaises(TypeError):
            ExecutionCapability()

    def test_incomplete_subclass_is_abstract(self):
        with self.assertRaises(TypeError):
            _IncompleteCapability()

    def test_complete_subclass_instantiates(self):
        capability = _EchoCapability()
        self.assertIsInstance(capability, ExecutionCapability)


# =====================================================================
# Statelessness & determinism (via the contract double)
# =====================================================================
class StatelessDeterminismTests(unittest.TestCase):
    def test_stateless(self):
        self.assertEqual(vars(_EchoCapability()), {})

    def test_deterministic(self):
        request = _request(capability_inputs={"a": 1})
        capability = _EchoCapability()
        self.assertEqual(capability.execute(request), capability.execute(request))

    def test_independent_instances_agree(self):
        request = _request(capability_inputs={"a": 1})
        self.assertEqual(
            _EchoCapability().execute(request),
            _EchoCapability().execute(request),
        )


# =====================================================================
# Dependency injection (composition root seam)
# =====================================================================
class CapabilityDependencyTests(unittest.TestCase):
    def test_get_execution_capability_raises_not_implemented(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import ExecutionCapabilityDep

        self.assertIsNotNone(ExecutionCapabilityDep)

    def test_existing_runtime_dependencies_unchanged(self):
        from app.core.dependencies import (
            get_execution_runtime,
            get_task_dispatcher,
        )
        from app.services.runtime.execution_runtime import ExecutionRuntime
        from app.services.runtime.task_dispatcher import TaskDispatcher

        self.assertIsInstance(get_execution_runtime(), ExecutionRuntime)
        self.assertIsInstance(get_task_dispatcher(), TaskDispatcher)


# =====================================================================
# Regression: existing provider seams unchanged
# =====================================================================
class SeamRegressionTests(unittest.TestCase):
    def test_tool_provider_seam_still_raises(self):
        from app.core.dependencies import get_tool_provider

        with self.assertRaises(NotImplementedError):
            get_tool_provider()

    def test_permission_provider_seam_still_raises(self):
        from app.core.dependencies import get_permission_provider

        with self.assertRaises(NotImplementedError):
            get_permission_provider()

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
