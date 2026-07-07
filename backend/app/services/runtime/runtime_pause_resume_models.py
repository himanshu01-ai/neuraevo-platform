"""Runtime pause/resume models (Sprint 14.12 — immutable pause/resume DTOs).

Provider-independent, immutable statement of *what pause/resume coordination the
runtime currently permits*: a pause/resume status plus the boolean capabilities
(pause, resume) and whether operator action is required. This COORDINATES
pause/resume state only; the state object executes nothing, pauses no thread or
process, and resumes nothing — it is derived from a runtime health snapshot.

Carries only plain data (ids, a label, bools) — no SDK, Runtime, Tool, capability,
or provider type crosses this boundary. Strictly additive to Sprints 14.1–14.11,
whose modules are left untouched. It knows nothing about any concrete capability.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class PauseResumeStatus(str, Enum):
    """The allowed, deterministic pause/resume statuses.

    ``RUNNING`` — active and may be paused. ``PAUSED`` — held and may be resumed.
    ``COMPLETED``/``FAILED``/``CANCELLED`` are terminal (no pause/resume applies).
    Kept as a ``str`` enum so each serialises to its label.
    """

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RuntimePauseResumeState(BaseModel):
    """Immutable pause/resume coordination state (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``pause_resume_status`` is one of the
    :class:`PauseResumeStatus` labels; ``can_pause``/``can_resume`` are the
    deterministic capabilities available in that status;
    ``requires_operator_action`` marks that a human operator must intervene; and
    ``pause_resume_metadata`` carries deterministic state descriptors. This is a
    coordination snapshot only — it pauses/resumes nothing and runs nothing.
    Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    pause_resume_status: str
    can_pause: bool
    can_resume: bool
    requires_operator_action: bool
    pause_resume_metadata: Dict[str, Any] = Field(default_factory=dict)
