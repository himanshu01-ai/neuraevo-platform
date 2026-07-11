"""Workflow coordinator (Sprint 15.15 — sequential multi-capability execution).

Defines :class:`WorkflowCoordinator`, the component that runs a sequence of
:class:`WorkflowStep` records over the existing Sprint 15 capabilities. For each step
it resolves the step's inputs against the running
:class:`WorkflowExecutionContext` (threading one capability's outputs and artifacts
into the next), dispatches the request through the injected
:class:`CapabilityRouter`, captures the outputs, shares the produced artifacts via the
injected :class:`ArtifactCoordinator`, and stops on the first unrecoverable failure —
returning a deterministic :class:`WorkflowExecutionResult`.

It contains no planning and no AI autonomy: the steps are given (Planning produces
them in an earlier layer). It validates the workflow, resolves and dispatches
capabilities through the router, handles failures deterministically, and never lets a
provider/SDK object escape — the router and capabilities keep everything behind the
plain :class:`ExecutionCapability` contract. Stateless beyond its injected
collaborators. Strictly additive to Sprints 15.1–15.14.
"""

from typing import Any, Dict, List, Optional

from app.services.runtime.artifact_coordinator import ArtifactCoordinator
from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionStatus,
)
from app.services.runtime.workflow_execution_context import WorkflowExecutionContext
from app.services.runtime.workflow_models import (
    ArtifactMissingError,
    CapabilityExecutionReference,
    CapabilityUnavailableError,
    WorkflowError,
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
    WorkflowValidationError,
)

_COMPLETED = CapabilityExecutionStatus.COMPLETED.value

# Pseudo-step id under which the workflow's seed inputs are exposed to bindings.
_INPUT_STEP = "input"


class WorkflowCoordinator:
    """Executes workflow steps in order, threading outputs and artifacts.

    Constructed with an injected :class:`CapabilityRouter` and
    :class:`ArtifactCoordinator` (constructor injection; it instantiates neither).
    ``execute`` validates the workflow, runs each step through the router, records a
    :class:`CapabilityExecutionReference` per step, shares artifacts, stops on the
    first failure, and returns a deterministic :class:`WorkflowExecutionResult`. It
    holds no mutable state between calls and performs no planning.
    """

    def __init__(
        self,
        router: CapabilityRouter,
        artifact_coordinator: ArtifactCoordinator,
    ) -> None:
        self.router = router
        self.artifact_coordinator = artifact_coordinator

    # --- public API ------------------------------------------------------
    def execute(
        self,
        steps: List[WorkflowStep],
        workflow_id: str = "workflow",
        runtime_id: str = "",
        execution_id: str = "",
        initial_inputs: Optional[Dict[str, Any]] = None,
    ) -> WorkflowExecutionResult:
        """Run ``steps`` sequentially and return a deterministic result.

        Validates the workflow first (a structural problem or an unavailable
        capability fails the whole workflow before any step runs). Then each step's
        inputs are resolved against prior results, dispatched through the router, and
        its outputs/artifacts folded into the context; execution stops on the first
        step that reports ``FAILED``. Never raises for user/step errors.
        """
        try:
            self._validate(steps)
        except WorkflowError as error:
            return self._failed(workflow_id, [], [], None, len(steps), str(error))

        seed = {_INPUT_STEP: dict(initial_inputs)} if initial_inputs else {}
        context = WorkflowExecutionContext(
            workflow_id=workflow_id, step_outputs=seed, total_steps=len(steps)
        )
        references: List[CapabilityExecutionReference] = []

        for index, step in enumerate(steps):
            try:
                inputs = self._resolve_inputs(step, context)
            except WorkflowError as error:
                return self._failed(
                    workflow_id, references, list(context.artifacts),
                    step.step_id, len(steps), str(error),
                )

            request = CapabilityExecutionRequest(
                runtime_id=runtime_id or workflow_id,
                execution_id=execution_id or workflow_id,
                execution_unit_id=step.step_id,
                capability_name=step.capability_name,
                capability_inputs=inputs,
                capability_metadata=dict(step.step_metadata),
            )
            try:
                result = self.router.dispatch(request)
            except WorkflowError as error:
                return self._failed(
                    workflow_id, references, list(context.artifacts),
                    step.step_id, len(steps), str(error),
                )

            completed = result.execution_status == _COMPLETED
            artifacts = self.artifact_coordinator.extract(
                step.step_id, step.capability_name, result.capability_outputs
            )
            references.append(
                CapabilityExecutionReference(
                    step_id=step.step_id,
                    capability_name=step.capability_name,
                    execution_status=result.execution_status,
                    outputs=dict(result.capability_outputs),
                    artifact_reference_ids=[a.reference_id for a in artifacts],
                    execution_metadata=dict(result.execution_metadata),
                )
            )
            context = context.record_step(
                step.step_id, result.capability_outputs, artifacts, index + 1, completed
            )
            if not completed:
                return self._failed(
                    workflow_id, references, list(context.artifacts),
                    step.step_id, len(steps),
                    f"step failed: {step.step_id}",
                )

        return self._completed(workflow_id, references, list(context.artifacts), len(steps))

    # --- validation ------------------------------------------------------
    def _validate(self, steps: List[WorkflowStep]) -> None:
        """Validate the workflow deterministically before any step runs."""
        if not steps:
            raise WorkflowValidationError("workflow has no steps")
        seen: List[str] = []
        for step in steps:
            if not step.step_id:
                raise WorkflowValidationError("every step needs a step_id")
            if step.step_id in seen:
                raise WorkflowValidationError(f"duplicate step id: {step.step_id}")
            if not self.router.is_available(step.capability_name):
                # deterministic failure surfaced before execution begins
                raise CapabilityUnavailableError(
                    f"capability unavailable: {step.capability_name}"
                )
            for dependency in step.depends_on:
                if dependency not in seen:
                    raise WorkflowValidationError(
                        f"invalid dependency in {step.step_id}: {dependency}"
                    )
            for reference in step.input_bindings.values():
                self._validate_binding_step(step.step_id, reference, seen)
            seen.append(step.step_id)

    @staticmethod
    def _validate_binding_step(
        step_id: str, reference: str, prior_steps: List[str]
    ) -> None:
        """Ensure an output binding refers to an earlier step (or the seed inputs)."""
        if not isinstance(reference, str) or not reference:
            raise WorkflowValidationError(f"invalid binding in {step_id}: {reference!r}")
        if reference.startswith("artifact:"):
            return  # artifact availability is validated at runtime (deterministic)
        source_step = reference.partition(".")[0]
        if source_step != _INPUT_STEP and source_step not in prior_steps:
            raise WorkflowValidationError(
                f"invalid dependency in {step_id}: {source_step}"
            )

    # --- input resolution -----------------------------------------------
    def _resolve_inputs(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> Dict[str, Any]:
        """Return the step's ``capability_inputs`` with bindings/artifacts resolved."""
        inputs: Dict[str, Any] = dict(step.inputs)
        for key, reference in step.input_bindings.items():
            inputs[key] = context.resolve_reference(reference)
        for artifact_id in step.required_artifacts:
            if context.find_artifact(artifact_id) is None:
                raise ArtifactMissingError(
                    f"required artifact missing: {artifact_id}"
                )
        return inputs

    # --- result builders -------------------------------------------------
    @staticmethod
    def _completed(workflow_id, references, artifacts, total) -> WorkflowExecutionResult:
        final_outputs = dict(references[-1].outputs) if references else {}
        return WorkflowExecutionResult(
            workflow_id=workflow_id,
            workflow_status=WorkflowStatus.COMPLETED.value,
            step_references=references,
            artifacts=artifacts,
            final_outputs=final_outputs,
            completed_step_count=len(references),
            total_step_count=total,
        )

    @staticmethod
    def _failed(
        workflow_id, references, artifacts, failed_step_id, total, error
    ) -> WorkflowExecutionResult:
        completed = [r for r in references if r.execution_status == _COMPLETED]
        final_outputs = dict(completed[-1].outputs) if completed else {}
        return WorkflowExecutionResult(
            workflow_id=workflow_id,
            workflow_status=WorkflowStatus.FAILED.value,
            step_references=references,
            artifacts=artifacts,
            final_outputs=final_outputs,
            failed_step_id=failed_step_id,
            completed_step_count=len(completed),
            total_step_count=total,
            result_metadata={"error": error},
        )
