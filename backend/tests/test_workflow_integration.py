"""Unit tests for the Sprint 15.15 Multi-Capability Workflow Integration.

Exercises the workflow coordination layer end to end without any network or SDK: the
offline, deterministic Sprint 15 capabilities (Python, File System, Email, Calendar,
GitHub) run in-process with temporary workspaces, and the Browser capability — which
would need a real browser — is represented by a deterministic stub
:class:`ExecutionCapability`, exactly the provider-independence the router relies on.

Covers:

* sequential execution and deterministic results;
* the required cross-capability flows — Browser→File System, Browser→Python,
  Python→File System, Python→Email, Calendar→Email, GitHub→File System;
* artifact passing (shared :class:`WorkflowArtifactReference` records, ``artifact:``
  bindings, ``required_artifacts``);
* capability routing (resolve / availability / dispatch);
* the execution context (immutable evolution + reference resolution);
* workflow validation (empty, duplicate ids, unknown capability, invalid dependency);
* failure propagation (stop on first failure, later steps not run);
* ExecutionCapability compliance and runtime-bridge JSON safety;
* the composition-root wiring; and
* regression that prior seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_workflow_integration
"""

import json
import shutil
import tempfile
import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.artifact_coordinator import ArtifactCoordinator
from app.services.runtime.calendar_capability import CalendarCapability
from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.email_capability import EmailCapability
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.filesystem_capability import FileSystemCapability
from app.services.runtime.github_capability import GitHubCapability
from app.services.runtime.python_capability import PythonCapability
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_execution_context import WorkflowExecutionContext
from app.services.runtime.workflow_models import (
    ArtifactMissingError,
    CapabilityExecutionReference,
    CapabilityUnavailableError,
    WorkflowArtifactReference,
    WorkflowBindingError,
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
    WorkflowValidationError,
)

_COMPLETED = CapabilityExecutionStatus.COMPLETED.value
_FAILED = CapabilityExecutionStatus.FAILED.value


class _StubBrowserCapability(ExecutionCapability):
    """Deterministic offline stand-in for the Browser capability.

    Returns fixed page content, a title, and one artifact — enough to drive the
    workflow coordination without a real browser (which needs network/Chromium).
    """

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_COMPLETED,
            capability_outputs={
                "page_content": "<html>Hello Workflow</html>",
                "title": "Demo Page",
                "payload": {"score": 7},
                "artifact": {
                    "artifact_id": "br-1",
                    "artifact_type": "PAGE",
                    "artifact_name": "page.html",
                    "artifact_path": "page.html",
                    "artifact_metadata": {"source": "stub"},
                },
            },
            execution_metadata={"operation": request.capability_inputs.get("operation")},
        )


class _FailingCapability(ExecutionCapability):
    """A capability that always fails — to test failure propagation."""

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_FAILED,
            capability_outputs={"error": "boom"},
            execution_metadata={},
        )


class _WorkflowTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="neuraevo_wf_")
        self.fs_root = tempfile.mkdtemp(prefix="neuraevo_wf_fs_")
        self.router = CapabilityRouter(
            {
                "browser": _StubBrowserCapability(),
                "python": PythonCapability(workspace_root=self.tmp + "/py"),
                "filesystem": FileSystemCapability(workspace_root=self.fs_root),
                "email": EmailCapability(staging_root=self.tmp + "/em"),
                "calendar": CalendarCapability(staging_root=self.tmp + "/cal"),
                "github": GitHubCapability(staging_root=self.tmp + "/gh"),
            }
        )
        self.coordinator = WorkflowCoordinator(self.router, ArtifactCoordinator())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.fs_root, ignore_errors=True)


# =====================================================================
# DTOs
# =====================================================================
class WorkflowDtoTests(unittest.TestCase):
    def test_status_enum(self):
        self.assertEqual(
            [s.value for s in WorkflowStatus],
            ["PENDING", "RUNNING", "COMPLETED", "FAILED"],
        )

    def test_dtos_are_immutable(self):
        step = WorkflowStep(step_id="s", capability_name="python")
        with self.assertRaises(ValidationError):
            step.capability_name = "email"
        with self.assertRaises(ValidationError):
            WorkflowArtifactReference(reference_id="r", artifact_id="a").artifact_id = "b"
        with self.assertRaises(ValidationError):
            CapabilityExecutionReference(
                step_id="s", capability_name="c", execution_status="COMPLETED"
            ).execution_status = "FAILED"
        with self.assertRaises(ValidationError):
            WorkflowExecutionResult(workflow_id="w", workflow_status="COMPLETED").workflow_status = "FAILED"

    def test_execution_context_is_immutable(self):
        context = WorkflowExecutionContext(workflow_id="w")
        with self.assertRaises(ValidationError):
            context.status = "FAILED"


# =====================================================================
# Capability router
# =====================================================================
class CapabilityRouterTests(_WorkflowTestBase):
    def test_available_capabilities(self):
        self.assertEqual(
            self.router.available_capabilities(),
            ["browser", "calendar", "email", "filesystem", "github", "python"],
        )

    def test_is_available(self):
        self.assertTrue(self.router.is_available("python"))
        self.assertFalse(self.router.is_available("slack"))

    def test_resolve_returns_execution_capability(self):
        capability = self.router.resolve("filesystem")
        self.assertIsInstance(capability, ExecutionCapability)

    def test_resolve_unknown_raises(self):
        with self.assertRaises(CapabilityUnavailableError):
            self.router.resolve("slack")

    def test_dispatch_executes_capability(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="python",
            capability_inputs={"python_code": "outputs['v'] = 5"},
        )
        result = self.router.dispatch(request)
        self.assertIsInstance(result, CapabilityExecutionResult)
        self.assertEqual(result.capability_outputs["execution_outputs"]["v"], 5)

    def test_dispatch_unknown_raises(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="slack",
        )
        with self.assertRaises(CapabilityUnavailableError):
            self.router.dispatch(request)


# =====================================================================
# Execution context
# =====================================================================
class ExecutionContextTests(unittest.TestCase):
    def test_record_step_returns_new_context(self):
        original = WorkflowExecutionContext(workflow_id="w", total_steps=1)
        updated = original.record_step("s1", {"content": "hi"}, [], 1, True)
        self.assertEqual(original.step_outputs, {})  # untouched
        self.assertEqual(updated.step_outputs["s1"], {"content": "hi"})
        self.assertEqual(updated.completed_steps, ["s1"])
        self.assertIsNot(updated, original)

    def test_resolve_output_reference(self):
        context = WorkflowExecutionContext(
            workflow_id="w",
            step_outputs={"reader": {"content": "data", "nested": {"k": [1, 2, 3]}}},
        )
        self.assertEqual(context.resolve_reference("reader.content"), "data")
        self.assertEqual(context.resolve_reference("reader.nested.k.2"), 3)
        self.assertEqual(context.resolve_reference("reader"), {"content": "data", "nested": {"k": [1, 2, 3]}})

    def test_resolve_input_seed(self):
        context = WorkflowExecutionContext(workflow_id="w", step_outputs={"input": {"x": 9}})
        self.assertEqual(context.resolve_reference("input.x"), 9)

    def test_resolve_unknown_step_raises(self):
        context = WorkflowExecutionContext(workflow_id="w")
        with self.assertRaises(WorkflowBindingError):
            context.resolve_reference("ghost.value")

    def test_resolve_missing_key_raises(self):
        context = WorkflowExecutionContext(workflow_id="w", step_outputs={"s": {"a": 1}})
        with self.assertRaises(WorkflowBindingError):
            context.resolve_reference("s.missing")

    def test_resolve_artifact_reference(self):
        artifact = WorkflowArtifactReference(
            reference_id="s:art-1", artifact_id="art-1", path="out.txt", name="out"
        )
        context = WorkflowExecutionContext(workflow_id="w", artifacts=[artifact])
        self.assertEqual(context.resolve_reference("artifact:art-1.path"), "out.txt")
        self.assertEqual(context.resolve_reference("artifact:s:art-1.name"), "out")

    def test_resolve_missing_artifact_raises(self):
        context = WorkflowExecutionContext(workflow_id="w")
        with self.assertRaises(ArtifactMissingError):
            context.resolve_reference("artifact:ghost")


# =====================================================================
# Artifact coordinator
# =====================================================================
class ArtifactCoordinatorTests(unittest.TestCase):
    def test_extract_single_artifact(self):
        coordinator = ArtifactCoordinator()
        refs = coordinator.extract(
            "step", "filesystem",
            {"artifact": {"artifact_id": "fs-1", "artifact_type": "CREATED", "artifact_path": "a.txt"}},
        )
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].reference_id, "step:fs-1")
        self.assertEqual(refs[0].path, "a.txt")
        self.assertEqual(refs[0].source_capability, "filesystem")

    def test_extract_list_artifacts(self):
        coordinator = ArtifactCoordinator()
        refs = coordinator.extract(
            "step", "python",
            {"artifacts": [{"artifact_id": "p-0"}, {"artifact_id": "p-1"}], "attachment_artifacts": [{"artifact_id": "att-0"}]},
        )
        self.assertEqual([r.artifact_id for r in refs], ["p-0", "p-1", "att-0"])

    def test_extract_ignores_malformed(self):
        coordinator = ArtifactCoordinator()
        self.assertEqual(coordinator.extract("s", "c", {"artifact": None}), [])
        self.assertEqual(coordinator.extract("s", "c", {"artifact": {"no_id": 1}}), [])
        self.assertEqual(coordinator.extract("s", "c", {}), [])

    def test_coordinator_is_stateless(self):
        self.assertEqual(vars(ArtifactCoordinator()), {})


# =====================================================================
# Sequential execution + cross-capability flows
# =====================================================================
class WorkflowExecutionTests(_WorkflowTestBase):
    def _run(self, steps, **kwargs):
        return self.coordinator.execute(steps, **kwargs)

    def test_browser_to_filesystem(self):
        result = self._run(
            [
                WorkflowStep(step_id="browse", capability_name="browser", inputs={"operation": "GET"}),
                WorkflowStep(
                    step_id="save", capability_name="filesystem",
                    inputs={"operation": "WRITE", "path": "page.txt"},
                    input_bindings={"content": "browse.page_content"},
                ),
            ],
            workflow_id="wf1",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertEqual(result.completed_step_count, 2)
        self.assertTrue(result.final_outputs["created"])
        # read it back to confirm the browser content was written
        read = self.router.dispatch(CapabilityExecutionRequest(
            runtime_id="r", execution_id="e", execution_unit_id="u",
            capability_name="filesystem",
            capability_inputs={"operation": "READ", "path": "page.txt"},
        ))
        self.assertEqual(read.capability_outputs["content"], "<html>Hello Workflow</html>")

    def test_browser_to_python(self):
        result = self._run(
            [
                WorkflowStep(step_id="browse", capability_name="browser", inputs={"operation": "GET"}),
                WorkflowStep(
                    step_id="py", capability_name="python",
                    inputs={"python_code": "outputs['upper'] = inputs['title'].upper()"},
                    input_bindings={"execution_inputs": "browse"},
                ),
            ],
            workflow_id="wf2",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertEqual(result.final_outputs["execution_outputs"]["upper"], "DEMO PAGE")

    def test_python_to_filesystem(self):
        result = self._run(
            [
                WorkflowStep(step_id="py", capability_name="python",
                             inputs={"python_code": "outputs['text'] = 'sum=' + str(1+2)"}),
                WorkflowStep(step_id="save", capability_name="filesystem",
                             inputs={"operation": "WRITE", "path": "r.txt"},
                             input_bindings={"content": "py.execution_outputs.text"}),
            ],
            workflow_id="wf3",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertEqual(result.final_outputs["bytes_written"], len("sum=3"))

    def test_python_to_email(self):
        result = self._run(
            [
                WorkflowStep(step_id="py", capability_name="python",
                             inputs={"python_code": "outputs['body'] = 'generated body'"}),
                WorkflowStep(step_id="send", capability_name="email",
                             inputs={"operation": "SEND", "subject": "Report", "to": ["a@x.com"]},
                             input_bindings={"body_text": "py.execution_outputs.body"}),
            ],
            workflow_id="wf4",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertIsNotNone(result.final_outputs["message_id"])

    def test_calendar_to_email(self):
        result = self._run(
            [
                WorkflowStep(step_id="ev", capability_name="calendar",
                             inputs={"operation": "CREATE", "summary": "Launch",
                                     "start_time": "2026-08-01T09:00:00", "end_time": "2026-08-01T10:00:00"}),
                WorkflowStep(step_id="notify", capability_name="email",
                             inputs={"operation": "SEND", "subject": "Created", "to": ["a@x.com"]},
                             input_bindings={"body_text": "ev.event.summary"}),
            ],
            workflow_id="wf5",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertIsNotNone(result.final_outputs["message_id"])

    def test_github_to_filesystem(self):
        result = self._run(
            [
                WorkflowStep(step_id="init", capability_name="github",
                             inputs={"operation": "INIT", "repository_name": "wf-repo"}),
                WorkflowStep(step_id="record", capability_name="filesystem",
                             inputs={"operation": "WRITE", "path": "repo.txt"},
                             input_bindings={"content": "init.repository.repository_id"}),
            ],
            workflow_id="wf6",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertTrue(result.step_references[0].outputs["repository"]["repository_id"].startswith("repo-"))

    def test_six_capability_sequential_chain(self):
        # A long deterministic chain touching several capabilities in order.
        steps = [
            WorkflowStep(step_id="browse", capability_name="browser", inputs={"operation": "GET"}),
            WorkflowStep(step_id="save", capability_name="filesystem",
                         inputs={"operation": "WRITE", "path": "page.txt"},
                         input_bindings={"content": "browse.page_content"}),
            WorkflowStep(step_id="py", capability_name="python",
                         inputs={"python_code": "outputs['n'] = len(inputs['page_content'])"},
                         input_bindings={"execution_inputs": "browse"}),
            WorkflowStep(step_id="gh", capability_name="github",
                         inputs={"operation": "INIT", "repository_name": "chain"}),
        ]
        result = self._run(steps, workflow_id="chain")
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertEqual(result.completed_step_count, 4)

    def test_determinism(self):
        steps = [
            WorkflowStep(step_id="py", capability_name="python",
                         inputs={"python_code": "outputs['v'] = sum(range(5))"}),
            WorkflowStep(step_id="save", capability_name="filesystem",
                         inputs={"operation": "WRITE", "path": "d.txt"},
                         input_bindings={"content": "py.stdout"}),
        ]
        a = self._run(steps, workflow_id="det")
        b = self._run(steps, workflow_id="det")
        self.assertEqual(a.workflow_status, b.workflow_status)
        self.assertEqual(a.completed_step_count, b.completed_step_count)
        self.assertEqual(
            [r.execution_status for r in a.step_references],
            [r.execution_status for r in b.step_references],
        )


# =====================================================================
# Artifact passing
# =====================================================================
class WorkflowArtifactPassingTests(_WorkflowTestBase):
    def test_artifacts_collected_from_steps(self):
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="browse", capability_name="browser", inputs={"operation": "GET"}),
                WorkflowStep(step_id="w", capability_name="filesystem",
                             inputs={"operation": "WRITE", "path": "a.txt", "content": "x"}),
            ],
            workflow_id="wf-art",
        )
        types = sorted(a.artifact_type for a in result.artifacts)
        self.assertIn("PAGE", types)
        self.assertIn("CREATED", types)

    def test_artifact_binding_passes_path_between_steps(self):
        # The browser artifact "br-1" has path "page.html"; a later Python step reads it.
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="browse", capability_name="browser", inputs={"operation": "GET"}),
                WorkflowStep(step_id="py", capability_name="python",
                             inputs={"python_code": "outputs['p'] = inputs['path']"},
                             input_bindings={"execution_inputs": "artifact:br-1"},
                             required_artifacts=["br-1"]),
            ],
            workflow_id="wf-art2",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)
        self.assertEqual(result.final_outputs["execution_outputs"]["p"], "page.html")

    def test_required_artifact_missing_fails(self):
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="py", capability_name="python",
                             inputs={"python_code": "outputs['x'] = 1"},
                             required_artifacts=["never-produced"]),
            ],
            workflow_id="wf-art3",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)
        self.assertIn("required artifact missing", result.result_metadata["error"])


# =====================================================================
# Validation + failure handling
# =====================================================================
class WorkflowValidationTests(_WorkflowTestBase):
    def test_empty_workflow_fails(self):
        result = self.coordinator.execute([], workflow_id="empty")
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)
        self.assertIn("no steps", result.result_metadata["error"])

    def test_duplicate_step_ids_fail(self):
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="s", capability_name="python", inputs={"python_code": "pass"}),
                WorkflowStep(step_id="s", capability_name="python", inputs={"python_code": "pass"}),
            ],
            workflow_id="dup",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)
        self.assertIn("duplicate step id", result.result_metadata["error"])

    def test_unavailable_capability_fails_before_execution(self):
        result = self.coordinator.execute(
            [WorkflowStep(step_id="s", capability_name="slack", inputs={})],
            workflow_id="unavail",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)
        self.assertIn("capability unavailable", result.result_metadata["error"])
        self.assertEqual(result.step_references, [])  # nothing ran

    def test_invalid_dependency_fails(self):
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="a", capability_name="python",
                             inputs={"python_code": "outputs['x']=1"},
                             input_bindings={"execution_inputs": "ghost.value"}),
            ],
            workflow_id="dep",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)
        self.assertIn("invalid dependency", result.result_metadata["error"])

    def test_declared_depends_on_must_be_earlier(self):
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="a", capability_name="python",
                             inputs={"python_code": "pass"}, depends_on=["later"]),
                WorkflowStep(step_id="later", capability_name="python", inputs={"python_code": "pass"}),
            ],
            workflow_id="order",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)

    def test_failure_propagation_stops_workflow(self):
        router = CapabilityRouter(
            {"failing": _FailingCapability(), "python": PythonCapability(workspace_root=self.tmp + "/p2")}
        )
        coordinator = WorkflowCoordinator(router, ArtifactCoordinator())
        result = coordinator.execute(
            [
                WorkflowStep(step_id="boom", capability_name="failing", inputs={}),
                WorkflowStep(step_id="never", capability_name="python", inputs={"python_code": "outputs['x']=1"}),
            ],
            workflow_id="fail",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)
        self.assertEqual(result.failed_step_id, "boom")
        self.assertEqual(len(result.step_references), 1)  # second step never ran
        self.assertEqual(result.completed_step_count, 0)

    def test_capability_reported_failure_propagates(self):
        # A real capability returning FAILED (bad email recipient) stops the workflow.
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="bad", capability_name="email",
                             inputs={"operation": "SEND", "subject": "x", "to": ["not-an-email"]}),
                WorkflowStep(step_id="after", capability_name="python", inputs={"python_code": "outputs['x']=1"}),
            ],
            workflow_id="fail2",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.FAILED.value)
        self.assertEqual(result.failed_step_id, "bad")
        self.assertEqual(len(result.step_references), 1)


# =====================================================================
# Compliance / JSON safety / plain DTOs
# =====================================================================
class WorkflowComplianceTests(_WorkflowTestBase):
    def test_router_dispatches_only_execution_capabilities(self):
        for name in self.router.available_capabilities():
            self.assertIsInstance(self.router.resolve(name), ExecutionCapability)

    def test_result_is_plain_dto(self):
        result = self.coordinator.execute(
            [WorkflowStep(step_id="py", capability_name="python", inputs={"python_code": "outputs['x']=1"})],
            workflow_id="plain",
        )
        self.assertIsInstance(result, WorkflowExecutionResult)
        self.assertIsInstance(result, BaseModel)

    def test_runtime_bridge_json_safety(self):
        result = self.coordinator.execute(
            [
                WorkflowStep(step_id="browse", capability_name="browser", inputs={"operation": "GET"}),
                WorkflowStep(step_id="gh", capability_name="github",
                             inputs={"operation": "INIT", "repository_name": "json-repo"}),
            ],
            workflow_id="json",
        )
        dumped = result.model_dump()
        json.dumps(dumped)  # must not raise
        self._assert_json_safe(dumped)

    def _assert_json_safe(self, value):
        if isinstance(value, dict):
            for item in value.values():
                self._assert_json_safe(item)
        elif isinstance(value, list):
            for item in value:
                self._assert_json_safe(item)
        else:
            self.assertNotIsInstance(value, (bytes, bytearray, BaseModel))


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class WorkflowDependencyInjectionTests(unittest.TestCase):
    def test_get_capability_router_registers_six_capabilities(self):
        from app.core.dependencies import get_capability_router

        router = get_capability_router()
        self.assertEqual(
            router.available_capabilities(),
            ["browser", "calendar", "email", "filesystem", "github", "python"],
        )

    def test_get_workflow_coordinator_returns_coordinator(self):
        from app.core.dependencies import get_workflow_coordinator

        self.assertIsInstance(get_workflow_coordinator(), WorkflowCoordinator)

    def test_deps_are_wired(self):
        from app.core.dependencies import (
            ArtifactCoordinatorDep,
            CapabilityRouterDep,
            WorkflowCoordinatorDep,
        )

        self.assertIn(CapabilityRouter, getattr(CapabilityRouterDep, "__args__", ()))
        self.assertIn(ArtifactCoordinator, getattr(ArtifactCoordinatorDep, "__args__", ()))
        self.assertIn(WorkflowCoordinator, getattr(WorkflowCoordinatorDep, "__args__", ()))

    def test_wired_coordinator_runs_a_workflow(self):
        from app.core.dependencies import get_workflow_coordinator

        coordinator = get_workflow_coordinator()
        result = coordinator.execute(
            [WorkflowStep(step_id="py", capability_name="python", inputs={"python_code": "outputs['ok']=True"})],
            workflow_id="di",
        )
        self.assertEqual(result.workflow_status, WorkflowStatus.COMPLETED.value)


# =====================================================================
# Regression — prior seams unchanged
# =====================================================================
class WorkflowRegressionTests(unittest.TestCase):
    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_capabilities_still_execution_capabilities(self):
        from app.core.dependencies import (
            get_browser_capability,
            get_calendar_capability,
            get_email_capability,
            get_filesystem_capability,
            get_github_capability,
            get_python_capability,
        )

        for provider in (
            get_browser_capability, get_python_capability, get_filesystem_capability,
            get_email_capability, get_calendar_capability, get_github_capability,
        ):
            self.assertIsInstance(provider(), ExecutionCapability)

    def test_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)


if __name__ == "__main__":
    unittest.main()
