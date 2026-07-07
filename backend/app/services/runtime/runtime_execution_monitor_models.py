"""Runtime execution monitor models (Sprint 14.11 — immutable health DTOs).

Provider-independent, immutable *health snapshot* of a runtime execution: a health
status, a deterministic health score, and any runtime warnings. This MONITORS
health only; the snapshot executes, dispatches, and changes nothing — it is
evaluated from a runtime state.

Carries only plain data (ids, a label, an int, plain string warnings) — no SDK,
Runtime, Tool, capability, or provider type crosses this boundary. Strictly
additive to Sprints 14.1–14.10, whose modules are left untouched. It knows nothing
about any concrete capability.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class RuntimeHealthStatus(str, Enum):
    """The allowed, deterministic runtime health statuses.

    ``HEALTHY`` — the runtime is initialising or running normally. ``WARNING`` —
    a non-fatal concern (e.g. cancellation). ``FAILED`` — execution failed.
    ``COMPLETED`` — execution completed. Kept as a ``str`` enum so each serialises
    to its label.
    """

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class RuntimeExecutionHealth(BaseModel):
    """Immutable runtime health snapshot for one execution (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``health_status`` is one of the
    :class:`RuntimeHealthStatus` labels; ``health_score`` is the deterministic
    ``0``–``100`` score for that status; ``runtime_warnings`` are the
    plain-language warnings (empty when healthy); and ``runtime_metadata`` carries
    deterministic state descriptors. This is a health snapshot only; producing it
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    health_status: str
    health_score: int
    runtime_warnings: List[str] = Field(default_factory=list)
    runtime_metadata: Dict[str, Any] = Field(default_factory=dict)
