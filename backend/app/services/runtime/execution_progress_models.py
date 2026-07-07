"""Execution progress models (Sprint 14.6 — immutable progress DTOs).

Provider-independent, immutable snapshot of *how far one execution pass has got*:
an overall progress status, the per-outcome unit counts, and a deterministic
integer completion percentage. This TRACKS progress only; the snapshot executes,
dispatches, and resolves nothing — it is aggregated from a capability execution
summary.

Carries only plain data (ids, a label, ints) — no SDK, Runtime, Tool, capability,
or provider type crosses this boundary. Strictly additive to Sprints 14.1–14.5,
whose modules are left untouched. It knows nothing about any concrete capability.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class ProgressStatus(str, Enum):
    """The allowed, deterministic execution-progress statuses.

    ``NOT_STARTED`` — nothing was executed. ``IN_PROGRESS`` — some units have not
    reached a terminal outcome. ``COMPLETED``/``FAILED``/``CANCELLED`` — every
    unit shared that terminal outcome. ``PARTIAL`` — every unit is terminal but
    the outcomes are mixed. Kept as a ``str`` enum so each serialises to its
    label.
    """

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"


class ExecutionProgress(BaseModel):
    """Immutable progress snapshot of one execution pass (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``progress_status`` is one of the
    :class:`ProgressStatus` labels; ``total_execution_units`` is the number of
    units the pass covered; ``completed_execution_units``,
    ``failed_execution_units``, and ``cancelled_execution_units`` are the
    per-outcome counts; ``completion_percentage`` is the deterministic integer
    ``completed / total * 100`` (0 when nothing ran); and ``progress_metadata``
    carries provider/telemetry data. This is a snapshot only; producing it
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    progress_status: str
    total_execution_units: int
    completed_execution_units: int
    failed_execution_units: int
    cancelled_execution_units: int
    completion_percentage: int
    progress_metadata: Dict[str, Any] = Field(default_factory=dict)
