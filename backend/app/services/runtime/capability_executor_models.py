"""Capability executor models (Sprint 14.5 — immutable execution-summary DTOs).

Provider-independent, immutable summary of *what happened when a capability was
invoked for each resolved assignment*: an overall status, the unit ids grouped by
outcome (completed/failed/cancelled), and the aggregated per-unit results. This
DESCRIBES an aggregate outcome; the summary object itself executes nothing — it is
produced from the results a capability already returned.

Carries only plain data plus the frozen Sprint 14.3 :class:`CapabilityExecution
Result` records — no SDK, Runtime, Tool, capability, or provider type crosses this
boundary. Strictly additive to Sprints 14.1–14.4, whose modules are left
untouched. The DTOs know nothing about any concrete capability.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.execution_capability_models import (
    CapabilityExecutionResult,
)


class ExecutionSummaryStatus(str, Enum):
    """The allowed, deterministic aggregate execution-summary statuses.

    ``COMPLETED`` — every invoked unit completed (or nothing was invoked).
    ``PARTIAL`` — a mix of outcomes. ``FAILED`` — every invoked unit failed.
    ``CANCELLED`` — every invoked unit was cancelled. Kept as a ``str`` enum so
    each serialises to its label.
    """

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CapabilityExecutionSummary(BaseModel):
    """Immutable aggregate of one execution pass over a dispatch plan (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``execution_status`` is one of the
    :class:`ExecutionSummaryStatus` labels; ``completed_execution_units``,
    ``failed_execution_units``, and ``cancelled_execution_units`` group the unit
    ids by outcome (in execution order); ``execution_results`` are the aggregated,
    ordered :class:`CapabilityExecutionResult` records; and ``execution_metadata``
    carries provider/telemetry data. This is an aggregate report only; producing
    it executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    execution_status: str
    completed_execution_units: List[str] = Field(default_factory=list)
    failed_execution_units: List[str] = Field(default_factory=list)
    cancelled_execution_units: List[str] = Field(default_factory=list)
    execution_results: List[CapabilityExecutionResult] = Field(
        default_factory=list
    )
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
