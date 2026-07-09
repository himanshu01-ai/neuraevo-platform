"""Python execution result model (Sprint 15.10 — immutable result DTO).

The immutable, provider-independent result of one Python execution: the status,
the captured stdout/stderr, the plain-data outputs, and the produced artifacts.
Kept in its own module (mirroring the browser layer's model split); it carries
only plain data — no interpreter frame, module, or SDK object crosses this
boundary. Strictly additive to Sprints 15.1–15.9, whose modules are left untouched.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.python_capability_models import PythonArtifact


class PythonExecutionResult(BaseModel):
    """Immutable result of one Python execution (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id``, ``execution_id``,
    and ``execution_unit_id`` echo the request's linkage; ``execution_status`` is
    one of the :class:`PythonExecutionStatus` labels; ``stdout``/``stderr`` are the
    captured streams; ``execution_outputs`` are the plain-data variables the code
    produced; ``artifacts`` are the :class:`PythonArtifact` records collected from
    the workspace; and ``execution_metadata`` carries deterministic descriptors
    only. Producing this DTO executes nothing further.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    execution_unit_id: str
    execution_status: str
    stdout: str = ""
    stderr: str = ""
    execution_outputs: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[PythonArtifact] = Field(default_factory=list)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
