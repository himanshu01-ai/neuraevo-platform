"""Python capability models (Sprint 15.10 — immutable Python-execution DTOs).

Provider-independent, immutable DTOs for the Python execution capability: an
execution request, an artifact descriptor, and a persistent workspace snapshot. A
:class:`PythonExecutionRequest` carries the code and inputs for one execution; a
:class:`PythonArtifact` describes one file the execution produced (never a file
handle or provider object); a :class:`PythonWorkspace` is an immutable snapshot of
the workspace's variables, artifacts, and execution history.

These carry only plain data across the boundary — no interpreter frame, module, or
SDK object ever appears. Strictly additive to Sprints 15.1–15.9, whose modules are
left untouched. The result DTO lives in
:mod:`app.services.runtime.python_execution_result`.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class PythonExecutionStatus(str, Enum):
    """The allowed, deterministic Python-execution statuses.

    ``READY`` — prepared to run. ``EXECUTING`` — running. ``COMPLETED`` /
    ``FAILED`` / ``CANCELLED`` are the terminal outcomes. Kept as a ``str`` enum so
    each serialises to its label; the labels match
    :class:`CapabilityExecutionStatus` so the runtime bridge is a pass-through.
    """

    READY = "READY"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PythonArtifact(BaseModel):
    """Immutable description of one artifact produced by an execution (no exec).

    ``frozen=True`` makes instances immutable. ``artifact_id`` is a deterministic
    identifier; ``artifact_type`` is a plain type label (``CSV``, ``EXCEL``,
    ``JSON``, ``PNG``, ``PDF``, ``TEXT``, …); ``artifact_name`` is the file name;
    ``artifact_path`` is the file's workspace path; and ``artifact_metadata``
    carries deterministic descriptors (never a file handle or provider object).
    Building this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    artifact_type: str
    artifact_name: str
    artifact_path: str
    artifact_metadata: Dict[str, Any] = Field(default_factory=dict)


class PythonExecutionRequest(BaseModel):
    """Immutable request to execute Python code (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``execution_unit_id`` names the unit;
    ``python_code`` is the code to run; ``execution_inputs`` are the plain inputs
    exposed to the code; and ``execution_metadata`` carries deterministic
    call-context descriptors. Building this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    execution_unit_id: str
    python_code: str
    execution_inputs: Dict[str, Any] = Field(default_factory=dict)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)


class PythonWorkspace(BaseModel):
    """Immutable snapshot of a Python execution workspace (no execution).

    ``frozen=True`` makes instances immutable — every execution produces a *new*
    workspace. ``workspace_id`` identifies it; ``variables`` are the persisted
    plain-data variables; ``artifacts`` are the accumulated :class:`PythonArtifact`
    records; ``execution_history`` is the ordered list of plain execution records;
    and ``workspace_metadata`` carries deterministic descriptors only. Producing
    this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    workspace_id: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[PythonArtifact] = Field(default_factory=list)
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)
    workspace_metadata: Dict[str, Any] = Field(default_factory=dict)
