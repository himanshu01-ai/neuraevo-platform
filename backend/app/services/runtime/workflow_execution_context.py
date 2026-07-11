"""Workflow execution context (Sprint 15.15 — externally-immutable workflow state).

Defines :class:`WorkflowExecutionContext`, the ExecutionContext component: it holds
the workflow's state (each step's plain outputs), stores the intermediate artifact
references, and tracks execution progress. It is *immutable externally* — every
update returns a *new* context (via :meth:`record_step`) rather than mutating the
existing one, mirroring the immutable workspace snapshots used across Sprint 15.

The context also knows how to resolve an input binding against its own state:
``"<step_id>.<dotted.path>"`` digs into a prior step's outputs, ``"input.<key>"``
reads the workflow's seed inputs, and ``"artifact:<id>[.field]"`` resolves a shared
artifact reference — so one capability's outputs become the next one's inputs. It
holds only plain data (dicts and :class:`WorkflowArtifactReference` descriptors) and
never a provider object. Strictly additive to Sprints 15.1–15.14.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.workflow_models import (
    ArtifactMissingError,
    WorkflowArtifactReference,
    WorkflowBindingError,
    WorkflowStatus,
)


class WorkflowExecutionContext(BaseModel):
    """Immutable snapshot of a workflow's state (the ExecutionContext component).

    ``frozen=True`` makes instances immutable — :meth:`record_step` returns a *new*
    context. ``workflow_id`` identifies the run; ``step_outputs`` maps each step id
    (and the pseudo-step ``"input"`` for seed inputs) to its plain outputs;
    ``artifacts`` are the accumulated :class:`WorkflowArtifactReference` records;
    ``completed_steps`` and ``current_step_index`` track progress; ``total_steps`` is
    the planned count; ``status`` is a :class:`WorkflowStatus` label; and
    ``context_metadata`` carries plain descriptors. It exposes no provider object.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: str
    step_outputs: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    artifacts: List[WorkflowArtifactReference] = Field(default_factory=list)
    completed_steps: List[str] = Field(default_factory=list)
    current_step_index: int = 0
    total_steps: int = 0
    status: str = WorkflowStatus.RUNNING.value
    context_metadata: Dict[str, Any] = Field(default_factory=dict)

    # --- immutable evolution --------------------------------------------
    def record_step(
        self,
        step_id: str,
        outputs: Dict[str, Any],
        artifacts: List[WorkflowArtifactReference],
        index: int,
        completed: bool,
    ) -> "WorkflowExecutionContext":
        """Return a *new* context with this step's outputs and artifacts folded in.

        The input context is only read — never mutated. ``completed`` marks whether
        the step succeeded (only successful steps join ``completed_steps``).
        """
        step_outputs = dict(self.step_outputs)
        step_outputs[step_id] = dict(outputs)
        completed_steps = list(self.completed_steps)
        if completed:
            completed_steps.append(step_id)
        return self.model_copy(
            update={
                "step_outputs": step_outputs,
                "artifacts": list(self.artifacts) + list(artifacts),
                "completed_steps": completed_steps,
                "current_step_index": index,
            }
        )

    # --- reference resolution -------------------------------------------
    def resolve_reference(self, reference: str) -> Any:
        """Resolve an input-binding ``reference`` against this context's state.

        ``"artifact:<id>[.field]"`` resolves a shared artifact reference (raising
        :class:`ArtifactMissingError` if unknown); otherwise the reference is
        ``"<step_id>.<dotted.path>"`` into a prior step's outputs (or the whole
        outputs dict when no path is given). Raises :class:`WorkflowBindingError`
        for an unknown step or a missing output path.
        """
        if not isinstance(reference, str) or not reference:
            raise WorkflowBindingError(f"invalid reference: {reference!r}")
        if reference.startswith("artifact:"):
            identifier, _, field = reference[len("artifact:"):].partition(".")
            artifact = self.find_artifact(identifier)
            if artifact is None:
                raise ArtifactMissingError(f"artifact not found: {identifier}")
            data = artifact.model_dump()
            return self._dig(data, field) if field else data
        step_id, separator, path = reference.partition(".")
        if step_id not in self.step_outputs:
            raise WorkflowBindingError(f"unknown step reference: {step_id}")
        outputs = self.step_outputs[step_id]
        return self._dig(outputs, path) if separator else dict(outputs)

    def find_artifact(self, identifier: str) -> Optional[WorkflowArtifactReference]:
        """Return the artifact matching ``identifier`` (reference id or artifact id)."""
        for artifact in self.artifacts:
            if identifier in (artifact.reference_id, artifact.artifact_id):
                return artifact
        return None

    # --- helpers --------------------------------------------------------
    @staticmethod
    def _dig(container: Any, path: str) -> Any:
        """Traverse a dotted ``path`` into nested dicts/lists (plain data only)."""
        current = container
        for token in path.split("."):
            if isinstance(current, dict):
                if token not in current:
                    raise WorkflowBindingError(f"missing output key: {token!r}")
                current = current[token]
            elif isinstance(current, list):
                try:
                    index = int(token)
                except ValueError:
                    raise WorkflowBindingError(f"invalid list index: {token!r}")
                if index < 0 or index >= len(current):
                    raise WorkflowBindingError(f"index out of range: {token!r}")
                current = current[index]
            else:
                raise WorkflowBindingError(
                    f"cannot index into {type(current).__name__} at {token!r}"
                )
        return current
