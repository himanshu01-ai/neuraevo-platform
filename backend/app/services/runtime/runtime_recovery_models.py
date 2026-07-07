"""Runtime recovery models (Sprint 14.13 — immutable recovery-state DTOs).

Provider-independent, immutable statement of *what runtime recovery is warranted*:
a recovery status, whether recovery is required, and the recovery strategy to
apply. This COORDINATES recovery readiness only; the state object executes
nothing, retries nothing, and resumes nothing — it is derived from a pause/resume
snapshot.

Carries only plain data (ids, labels, a bool) — no SDK, Runtime, Tool, capability,
or provider type crosses this boundary. Strictly additive to Sprints 14.1–14.12,
whose modules are left untouched. It knows nothing about any concrete capability.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class RecoveryStatus(str, Enum):
    """The allowed, deterministic runtime recovery statuses.

    ``NOT_REQUIRED`` — no recovery is warranted. ``READY`` — recovery can proceed.
    ``RECOVERING`` — recovery is under way. ``FAILED`` — recovery cannot proceed
    automatically. Kept as a ``str`` enum so each serialises to its label.
    """

    NOT_REQUIRED = "NOT_REQUIRED"
    READY = "READY"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"


class RecoveryStrategy(str, Enum):
    """The allowed, deterministic recovery strategies.

    ``NONE`` — nothing to recover. ``RESUME`` — resume from where it paused.
    ``RESTART`` — restart the execution. ``MANUAL`` — a human operator must
    intervene. Kept as a ``str`` enum so each serialises to its label.
    """

    NONE = "NONE"
    RESUME = "RESUME"
    RESTART = "RESTART"
    MANUAL = "MANUAL"


class RuntimeRecoveryState(BaseModel):
    """Immutable runtime recovery coordination state (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``recovery_status`` is one of the
    :class:`RecoveryStatus` labels; ``recovery_required`` marks that recovery is
    warranted; ``recovery_strategy`` is one of the :class:`RecoveryStrategy`
    labels; and ``recovery_metadata`` carries deterministic state descriptors.
    This is a coordination snapshot only — it recovers, retries, and resumes
    nothing. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    recovery_status: str
    recovery_required: bool
    recovery_strategy: str
    recovery_metadata: Dict[str, Any] = Field(default_factory=dict)
