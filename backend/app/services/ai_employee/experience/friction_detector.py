"""Friction detector (Sprint 16.12 — detect workflow friction deterministically).

Defines :class:`FrictionDetector`, which detects workflow friction by *reading*
observed task state against fixed thresholds — never by instrumenting execution. It
detects frequent failures, repeated retries, long workflows, abandoned tasks, and a
high cancellation rate, reporting each above-threshold concern as a
:class:`FrictionPoint` inside an immutable :class:`FrictionReport`.

The thresholds are injected at construction (deterministic defaults otherwise); the
detection is a fixed rule-based function of the observed rates (no AI, no learning, no
prediction). It reads only observed task state passed in or read from the frozen
Sprint 16.10 :class:`AIEmployeeService`; it observes only and executes, delegates, and
stores nothing, and it never modifies AI behaviour. Strictly additive to Sprints
1.x–16.11, whose modules are left untouched.
"""

from typing import List, Optional

from app.services.ai_employee.experience import signals
from app.services.ai_employee.experience.models import (
    FrictionPoint,
    FrictionReport,
    FrictionSeverity,
    FrictionType,
)
from app.services.ai_employee.service import (
    AIEmployeeService,
    TaskStatusResponse,
)

# Ordering of severities so the report can pick the maximum deterministically.
_SEVERITY_ORDER = {
    FrictionSeverity.NONE: 0,
    FrictionSeverity.LOW: 1,
    FrictionSeverity.MEDIUM: 2,
    FrictionSeverity.HIGH: 3,
}


class FrictionDetector:
    """Detects workflow friction against fixed thresholds (no execution).

    Constructed with an injected :class:`AIEmployeeService` plus deterministic rate
    thresholds and a long-workflow step threshold (constructor injection; it
    instantiates none). ``detect`` reads the observed tasks and reports each
    above-threshold concern as a :class:`FrictionPoint`. It is stateless, reads only,
    and runs nothing.
    """

    def __init__(
        self,
        service: AIEmployeeService,
        medium_rate: float = 0.25,
        high_rate: float = 0.5,
        long_workflow_units: int = 8,
    ) -> None:
        self.service = service
        self.medium_rate = medium_rate
        self.high_rate = high_rate
        self.long_workflow_units = long_workflow_units

    def detect(
        self, tasks: Optional[List[TaskStatusResponse]] = None
    ) -> FrictionReport:
        """Return the :class:`FrictionReport` for the observed tasks.

        Analyses the supplied ``tasks`` when given, else the service's live task list.
        An empty observation set reports no friction. Deterministic; it runs nothing.
        """
        observed = signals.resolve_tasks(self.service, tasks)
        count = len(observed)
        if count == 0:
            return FrictionReport(summary="no task activity observed")

        failure_rate = self._rate(observed, signals.failed)
        retry_rate = self._rate(
            observed, lambda task: signals.retry_count(task) > 0
        )
        long_rate = self._rate(
            observed,
            lambda task: signals.execution_units(task)
            >= self.long_workflow_units,
        )
        abandoned_rate = self._rate(observed, signals.abandoned)
        cancellation_rate = self._rate(observed, signals.cancelled)

        candidates = [
            (
                FrictionType.FREQUENT_FAILURES,
                failure_rate,
                "task failure rate",
            ),
            (
                FrictionType.REPEATED_RETRIES,
                retry_rate,
                "share of tasks retried",
            ),
            (
                FrictionType.LONG_WORKFLOWS,
                long_rate,
                f"share of workflows >= {self.long_workflow_units} steps",
            ),
            (
                FrictionType.ABANDONED_TASKS,
                abandoned_rate,
                "share of tasks abandoned",
            ),
            (
                FrictionType.HIGH_CANCELLATION,
                cancellation_rate,
                "task cancellation rate",
            ),
        ]

        points: List[FrictionPoint] = []
        for friction_type, rate, label in candidates:
            severity = self._severity(rate)
            if severity == FrictionSeverity.NONE:
                continue
            points.append(
                FrictionPoint(
                    friction_type=friction_type,
                    severity=severity,
                    detail=f"{label} is {round(rate, 4)}",
                    metric=round(rate, 4),
                )
            )

        highest = self._highest(points)
        return FrictionReport(
            friction_detected=bool(points),
            points=points,
            highest_severity=highest,
            summary=(
                f"{len(points)} friction point(s); highest severity "
                f"{highest.value}"
                if points
                else "no friction detected"
            ),
            report_metadata={"observed_tasks": count},
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _rate(tasks: List[TaskStatusResponse], predicate) -> float:
        """Return the fraction of ``tasks`` satisfying ``predicate``."""
        count = len(tasks)
        if count == 0:
            return 0.0
        return sum(1 for task in tasks if predicate(task)) / count

    def _severity(self, rate: float) -> FrictionSeverity:
        """Return the deterministic :class:`FrictionSeverity` for ``rate``."""
        if rate >= self.high_rate:
            return FrictionSeverity.HIGH
        if rate >= self.medium_rate:
            return FrictionSeverity.MEDIUM
        if rate > 0.0:
            return FrictionSeverity.LOW
        return FrictionSeverity.NONE

    @staticmethod
    def _highest(points: List[FrictionPoint]) -> FrictionSeverity:
        """Return the maximum severity across ``points`` (``NONE`` when empty)."""
        highest = FrictionSeverity.NONE
        for point in points:
            if _SEVERITY_ORDER[point.severity] > _SEVERITY_ORDER[highest]:
                highest = point.severity
        return highest
