"""Execution monitor models (Sprint 13.12 — immutable monitoring DTOs).

Provider-independent, immutable *observation* of an in-flight execution: an
overall status label, a completion percentage, the node ids grouped by whether
they are active, blocked, completed, or pending, a derived health status, and
plain-language warnings. This OBSERVES execution; it never executes, resolves,
schedules, or acquires anything — no execution layer exists.

Carries only plain data (ids, labels, a float, plain string lists) — no SDK,
Runtime, Tool, or Planner-framework type crosses this boundary. Strictly additive
to Sprints 13.1–13.11, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class ExecutionHealthStatus(str, Enum):
    """The allowed, deterministic execution health statuses.

    ``HEALTHY`` means work is progressing normally; ``WARNING`` flags a mixed or
    transitional condition; ``BLOCKED`` means blocked work is preventing
    progress; ``COMPLETED`` and ``FAILED`` are the terminal outcomes. Kept as a
    ``str`` enum so each serialises to its label.
    """

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExecutionMonitoringReport(BaseModel):
    """Immutable observation of an execution's progress and health (no execution).

    ``frozen=True`` makes instances immutable. ``report_id`` is a deterministic
    identifier; ``execution_id`` links to the observed execution;
    ``execution_status`` echoes the aggregate execution-state label;
    ``overall_progress`` is the ``0.0``–``100.0`` completion percentage taken from
    the execution state; ``active_nodes``/``blocked_nodes``/``completed_nodes``/
    ``pending_nodes`` group the node ids by observed status (a forward-looking
    schedule lists no completed nodes, so ``completed_nodes`` is normally empty);
    ``health_status`` is one of the :class:`ExecutionHealthStatus` labels;
    ``warnings`` carries plain-language diagnostics; and ``metadata`` carries
    provider/telemetry data. The value types are intentionally plain — permissive
    lists of ids and a float — so the :class:`PlanValidator` is the single place
    the domain rules (valid status/health, progress range, disjoint node groups,
    health/status consistency) are enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    report_id: str
    execution_id: str
    execution_status: str
    overall_progress: float
    active_nodes: List[str] = Field(default_factory=list)
    blocked_nodes: List[str] = Field(default_factory=list)
    completed_nodes: List[str] = Field(default_factory=list)
    pending_nodes: List[str] = Field(default_factory=list)
    health_status: str
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
