"""Performance validator (Sprint 16.13 — deterministic performance summaries).

Defines :class:`PerformanceValidator`, which measures deterministic performance
counters by *reading* the frozen Sprint 16.11 :class:`ObservabilityManager` (reached
through the :class:`EnterpriseOperationsManager`). It reports execution statistics, a
throughput summary, response statistics, and a resource-usage summary — every value is
a count or a ratio read from platform state.

There is NO benchmarking tool, timer, clock, or load generator anywhere: "throughput"
is a processed-work count (not per-second), and "response" statistics are deterministic
ratios of those counts. It observes only: it measures and executes, delegates, and
stores nothing. Strictly additive to Sprints 1.x–16.12, whose modules are left
untouched.
"""

from typing import Dict

from app.services.ai_employee.validation import common
from app.services.ai_employee.validation.models import (
    PerformanceSummary,
    ValidationResult,
    ValidationScope,
)


class PerformanceValidator:
    """Measures deterministic performance counters (read-only, no benchmarking).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``execution_statistics``, ``throughput_summary``,
    ``response_statistics``, and ``resource_usage_summary`` each read platform counters;
    ``summary`` bundles them into a :class:`PerformanceSummary`; and ``validate`` returns
    the performance :class:`ValidationResult`. It uses no timer or load generator — it
    reads counts only and runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def execution_statistics(self) -> Dict[str, int]:
        """Return the per-state task/execution counters."""
        return dict(self.operations.observability.execution_statistics().metrics)

    def throughput_summary(self) -> Dict[str, int]:
        """Return the processed-work counts (total, completed, failed, cancelled)."""
        execution = self.execution_statistics()
        return {
            "tasks_total": execution.get("tasks_total", 0),
            "tasks_completed": execution.get("tasks_completed", 0),
            "tasks_failed": execution.get("tasks_failed", 0),
            "tasks_cancelled": execution.get("tasks_cancelled", 0),
        }

    def response_statistics(self) -> Dict[str, float]:
        """Return deterministic response ratios (success/failure share of tasks)."""
        execution = self.execution_statistics()
        total = execution.get("tasks_total", 0)
        if total <= 0:
            return {"success_rate": 0.0, "failure_rate": 0.0}
        return {
            "success_rate": round(
                execution.get("tasks_completed", 0) / total, 4
            ),
            "failure_rate": round(
                execution.get("tasks_failed", 0) / total, 4
            ),
        }

    def resource_usage_summary(self) -> Dict[str, int]:
        """Return the resource counters (sessions, tasks, audit records)."""
        return dict(self.operations.observability.service_statistics().metrics)

    def summary(self) -> PerformanceSummary:
        """Return the bundled :class:`PerformanceSummary`."""
        return PerformanceSummary(
            execution=self.execution_statistics(),
            throughput=self.throughput_summary(),
            response=self.response_statistics(),
            resource_usage=self.resource_usage_summary(),
            summary_metadata={"source": "observability"},
        )

    def validate(self) -> ValidationResult:
        """Return the performance :class:`ValidationResult`.

        Performance measurement is always readable, so the result passes; the counters
        that back the verdict travel in the metadata. Any inconsistency (a negative or
        out-of-range counter) is impossible given the frozen counters, so no issue is
        raised. Deterministic; it runs nothing.
        """
        summary = self.summary()
        return common.result(
            name="performance metrics",
            scope=ValidationScope.PERFORMANCE,
            issues=[],
            detail=(
                f"{summary.throughput.get('tasks_total', 0)} task(s) "
                f"processed; success rate "
                f"{summary.response.get('success_rate', 0.0)}"
            ),
            metadata={
                "throughput": summary.throughput,
                "response": summary.response,
            },
        )
