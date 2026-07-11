"""Artifact coordinator (Sprint 15.15 — share artifacts between capabilities).

Defines :class:`ArtifactCoordinator`, the component that turns the artifact
descriptors inside a capability's plain outputs into shared
:class:`WorkflowArtifactReference` records, so a later step can reference an artifact
an earlier capability produced. It reads only the already-plain ``capability_outputs``
(each capability's ``execute`` bridge emits plain, JSON-safe dicts) — it never opens a
file, contacts a provider, or exposes a provider/SDK object.

It is responsible *only* for artifact references: it extracts them and maintains
their references; it performs no capability execution, no workflow ordering, and no
planning. Deterministic and offline; stateless — it holds nothing between calls.
Strictly additive to Sprints 15.1–15.14.
"""

from typing import Any, Dict, List, Optional

from app.services.runtime.workflow_models import WorkflowArtifactReference

# The output keys under which the Sprint 15 capabilities expose artifacts: a single
# ``artifact`` (File System / Calendar / GitHub / Email send), a list of
# ``artifacts`` (Python), or ``attachment_artifacts`` (Email uploads).
_SINGLE_KEYS = ("artifact",)
_LIST_KEYS = ("artifacts", "attachment_artifacts")


class ArtifactCoordinator:
    """Stateless coordinator that shares artifacts between capabilities.

    ``extract`` scans one step's plain outputs for artifact descriptors and returns
    deterministic :class:`WorkflowArtifactReference` records; ``find`` locates a
    reference within a list by reference id or artifact id. It reads only plain data
    and exposes no provider object.
    """

    def extract(
        self,
        step_id: str,
        capability_name: str,
        outputs: Dict[str, Any],
    ) -> List[WorkflowArtifactReference]:
        """Return the artifact references found in ``outputs`` (deterministic order).

        Scans the single-artifact key then the list keys; each descriptor is
        normalised into a plain :class:`WorkflowArtifactReference`. Malformed or
        empty descriptors (no ``artifact_id``) are skipped. Reads no file contents.
        """
        references: List[WorkflowArtifactReference] = []
        for key in _SINGLE_KEYS:
            reference = self._to_reference(step_id, capability_name, outputs.get(key))
            if reference is not None:
                references.append(reference)
        for key in _LIST_KEYS:
            for descriptor in outputs.get(key) or []:
                reference = self._to_reference(step_id, capability_name, descriptor)
                if reference is not None:
                    references.append(reference)
        return references

    @staticmethod
    def find(
        references: List[WorkflowArtifactReference], identifier: str
    ) -> Optional[WorkflowArtifactReference]:
        """Return the reference matching ``identifier`` (reference id or artifact id)."""
        for reference in references:
            if identifier in (reference.reference_id, reference.artifact_id):
                return reference
        return None

    @staticmethod
    def _to_reference(
        step_id: str, capability_name: str, descriptor: Any
    ) -> Optional[WorkflowArtifactReference]:
        """Normalise one plain artifact descriptor into a reference (or ``None``)."""
        if not isinstance(descriptor, dict):
            return None
        artifact_id = descriptor.get("artifact_id")
        if not artifact_id:
            return None
        return WorkflowArtifactReference(
            reference_id=f"{step_id}:{artifact_id}",
            artifact_id=artifact_id,
            artifact_type=descriptor.get("artifact_type", "UNKNOWN"),
            name=descriptor.get("artifact_name")
            or descriptor.get("name")
            or artifact_id,
            source_step=step_id,
            source_capability=capability_name,
            path=descriptor.get("artifact_path") or descriptor.get("path"),
            reference_metadata=dict(descriptor.get("artifact_metadata") or {}),
        )
