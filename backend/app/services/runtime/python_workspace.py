"""Python workspace manager (Sprint 15.10 — immutable workspace lifecycle).

Creates and evolves immutable :class:`PythonWorkspace` snapshots: variables,
accumulated artifacts, and an ordered execution history. The workspace is
immutable, so ``record_execution`` returns a *new* workspace rather than mutating
the given one. It manages workspace state only — it never executes Python and
never touches a provider.

Deterministic and offline. Stateless — it holds nothing between calls. Strictly
additive to Sprints 15.1–15.9, whose modules are left untouched.
"""

from typing import Any, Dict, List

from app.services.runtime.python_capability_models import (
    PythonArtifact,
    PythonExecutionRequest,
    PythonWorkspace,
)


class PythonWorkspaceManager:
    """Stateless manager of immutable :class:`PythonWorkspace` snapshots.

    ``create_workspace`` mints an empty workspace; ``record_execution`` folds one
    execution's outputs, artifacts, and history entry into a *new* workspace,
    leaving the input untouched. It never executes Python.
    """

    def create_workspace(self, workspace_id: str) -> PythonWorkspace:
        """Return a fresh, empty :class:`PythonWorkspace` for ``workspace_id``."""
        return PythonWorkspace(
            workspace_id=workspace_id,
            variables={},
            artifacts=[],
            execution_history=[],
            workspace_metadata={"execution_count": 0},
        )

    def record_execution(
        self,
        workspace: PythonWorkspace,
        *,
        request: PythonExecutionRequest,
        execution_outputs: Dict[str, Any],
        artifacts: List[PythonArtifact],
        status: str,
    ) -> PythonWorkspace:
        """Return a new workspace with this execution folded in (immutable).

        Merges ``execution_outputs`` into the persisted variables, appends the
        artifacts and a deterministic history entry, and increments the execution
        count. The input ``workspace`` is only read — never mutated.
        """
        entry: Dict[str, Any] = {
            "execution_id": request.execution_id,
            "execution_unit_id": request.execution_unit_id,
            "status": status,
            "output_count": len(execution_outputs),
            "artifact_count": len(artifacts),
        }
        return PythonWorkspace(
            workspace_id=workspace.workspace_id,
            variables={**workspace.variables, **execution_outputs},
            artifacts=list(workspace.artifacts) + list(artifacts),
            execution_history=list(workspace.execution_history) + [entry],
            workspace_metadata={
                **workspace.workspace_metadata,
                "execution_count": workspace.workspace_metadata.get(
                    "execution_count", 0
                )
                + 1,
            },
        )
