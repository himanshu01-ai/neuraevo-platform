"""Unit tests for the Sprint 14.6 Execution Progress Runtime.

Covers the progress-tracking layer end to end without touching any network, SDK,
AI, clock, UUID, capability, execution, or database:

* the immutable :class:`ExecutionProgress` DTO and the :class:`ProgressStatus`
  enum (defaults, immutability, required fields, enum values);
* the deterministic, stateless :class:`ExecutionProgressRuntime` (aggregation,
  integer completion percentage, all status derivations, empty summary,
  determinism, statelessness, non-mutation, provider independence);
* the composition-root wiring (``get_execution_progress_runtime`` +
  ``ExecutionProgressRuntimeDep``); and
* regression that the Sprint 14.5 executor and Sprint 13 pipeline are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_progress_runtime
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.capability_executor_models import (
    CapabilityExecutionSummary,
)
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionResult,
)
from app.services.runtime.execution_progress_models import (
    ExecutionProgress,
    ProgressStatus,
)
from app.services.runtime.execution_progress_runtime import (
    ExecutionProgressRuntime,
)


# =====================================================================
# Helpers
# =====================================================================
def _result(unit_id, status):
    return CapabilityExecutionResult(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        execution_unit_id=unit_id,
        capability_name=f"capability-{unit_id}",
        execution_status=status,
        capability_outputs={},
        execution_metadata={},
    )


def _summary(
    completed=(),
    failed=(),
    cancelled=(),
    in_progress=(),
    status="COMPLETED",
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    results = (
        [_result(u, "COMPLETED") for u in completed]
        + [_result(u, "FAILED") for u in failed]
        + [_result(u, "CANCELLED") for u in cancelled]
        + [_result(u, "EXECUTING") for u in in_progress]
    )
    return CapabilityExecutionSummary(
        runtime_id=runtime_id,
        execution_id=execution_id,
        execution_status=status,
        completed_execution_units=list(completed),
        failed_execution_units=list(failed),
        cancelled_execution_units=list(cancelled),
        execution_results=results,
        execution_metadata={},
    )


def _progress(summary=None):
    return ExecutionProgressRuntime().create_progress(
        summary if summary is not None else _summary(completed=("u1",))
    )


def _model(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        progress_status="COMPLETED",
        total_execution_units=1,
        completed_execution_units=1,
        failed_execution_units=0,
        cancelled_execution_units=0,
        completion_percentage=100,
        progress_metadata={},
    )
    data.update(overrides)
    return ExecutionProgress(**data)


# =====================================================================
# DTOs
# =====================================================================
class ProgressModelTests(unittest.TestCase):
    def test_defaults(self):
        progress = ExecutionProgress(
            runtime_id="r",
            execution_id="e",
            progress_status="NOT_STARTED",
            total_execution_units=0,
            completed_execution_units=0,
            failed_execution_units=0,
            cancelled_execution_units=0,
            completion_percentage=0,
        )
        self.assertEqual(progress.progress_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionProgress(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _model().progress_status = "FAILED"
        with self.assertRaises(ValidationError):
            _model().completion_percentage = 50

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in ProgressStatus},
            {
                "NOT_STARTED",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                "PARTIAL",
            },
        )

    def test_produces_progress(self):
        self.assertIsInstance(_progress(), ExecutionProgress)


# =====================================================================
# Status derivation (the deterministic rules)
# =====================================================================
class StatusDerivationTests(unittest.TestCase):
    def test_empty_summary_is_not_started(self):
        progress = _progress(_summary())
        self.assertEqual(progress.progress_status, "NOT_STARTED")
        self.assertEqual(progress.total_execution_units, 0)

    def test_all_completed_is_completed(self):
        self.assertEqual(
            _progress(_summary(completed=("a", "b", "c"))).progress_status,
            "COMPLETED",
        )

    def test_all_failed_is_failed(self):
        self.assertEqual(
            _progress(_summary(failed=("a", "b"))).progress_status, "FAILED"
        )

    def test_all_cancelled_is_cancelled(self):
        self.assertEqual(
            _progress(_summary(cancelled=("a", "b"))).progress_status,
            "CANCELLED",
        )

    def test_mixed_terminal_is_partial(self):
        self.assertEqual(
            _progress(
                _summary(completed=("a",), failed=("b",), cancelled=("c",))
            ).progress_status,
            "PARTIAL",
        )

    def test_completed_failed_mix_is_partial(self):
        self.assertEqual(
            _progress(_summary(completed=("a", "b"), failed=("c",))).progress_status,
            "PARTIAL",
        )

    def test_non_terminal_is_in_progress(self):
        self.assertEqual(
            _progress(
                _summary(completed=("a",), in_progress=("b",))
            ).progress_status,
            "IN_PROGRESS",
        )


# =====================================================================
# Completion percentage (deterministic integer rounding)
# =====================================================================
class CompletionPercentageTests(unittest.TestCase):
    def test_zero_when_empty(self):
        self.assertEqual(_progress(_summary()).completion_percentage, 0)

    def test_hundred_when_all_completed(self):
        self.assertEqual(
            _progress(_summary(completed=("a", "b"))).completion_percentage, 100
        )

    def test_zero_when_all_failed(self):
        self.assertEqual(
            _progress(_summary(failed=("a", "b"))).completion_percentage, 0
        )

    def test_rounds_deterministically(self):
        # completed / total * 100 with pure-integer round-half-up.
        cases = {
            (1, 3): 33,   # 33.33 -> 33
            (2, 3): 67,   # 66.67 -> 67
            (1, 4): 25,
            (3, 4): 75,
            (1, 2): 50,
            (1, 8): 13,   # 12.5 -> 13 (round-half-up)
        }
        for (completed, total), expected in cases.items():
            failed = total - completed
            with self.subTest(completed=completed, total=total):
                progress = _progress(
                    _summary(
                        completed=tuple(f"c{i}" for i in range(completed)),
                        failed=tuple(f"f{i}" for i in range(failed)),
                    )
                )
                self.assertEqual(progress.completion_percentage, expected)


# =====================================================================
# Counts, determinism, non-mutation & provider independence
# =====================================================================
class AggregationTests(unittest.TestCase):
    def test_preserves_counts(self):
        progress = _progress(
            _summary(completed=("a", "b"), failed=("c",), cancelled=("d",))
        )
        self.assertEqual(progress.total_execution_units, 4)
        self.assertEqual(progress.completed_execution_units, 2)
        self.assertEqual(progress.failed_execution_units, 1)
        self.assertEqual(progress.cancelled_execution_units, 1)

    def test_ids_and_metadata_from_summary(self):
        progress = _progress(_summary(completed=("a",), in_progress=("b",)))
        self.assertEqual(progress.runtime_id, "runtime-exec-x")
        self.assertEqual(progress.execution_id, "exec-x")
        self.assertEqual(progress.progress_metadata["in_progress"], 1)

    def test_deterministic(self):
        summary = _summary(completed=("a",), failed=("b",))
        runtime = ExecutionProgressRuntime()
        self.assertEqual(
            runtime.create_progress(summary), runtime.create_progress(summary)
        )

    def test_independent_runtimes_agree(self):
        summary = _summary(completed=("a", "b"))
        self.assertEqual(
            ExecutionProgressRuntime().create_progress(summary),
            ExecutionProgressRuntime().create_progress(summary),
        )

    def test_does_not_mutate_summary(self):
        summary = _summary(completed=("a",), failed=("b",))
        before = summary.model_dump()
        _progress(summary)
        self.assertEqual(summary.model_dump(), before)

    def test_plain_data_only(self):
        progress = _progress(_summary(completed=("a",), failed=("b",)))
        plain = (str, int, float, bool, type(None))
        for value in progress.progress_metadata.values():
            self.assertIsInstance(value, plain)


# =====================================================================
# Statelessness
# =====================================================================
class StatelessTests(unittest.TestCase):
    def test_stateless(self):
        self.assertEqual(vars(ExecutionProgressRuntime()), {})

    def test_no_state_accumulates(self):
        runtime = ExecutionProgressRuntime()
        runtime.create_progress(_summary(completed=("a",)))
        self.assertEqual(vars(runtime), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ProgressDependencyTests(unittest.TestCase):
    def test_get_runtime_returns_runtime(self):
        from app.core.dependencies import get_execution_progress_runtime

        self.assertIsInstance(
            get_execution_progress_runtime(), ExecutionProgressRuntime
        )

    def test_get_runtime_is_stateless(self):
        from app.core.dependencies import get_execution_progress_runtime

        self.assertEqual(vars(get_execution_progress_runtime()), {})

    def test_injected_runtime_creates_progress(self):
        from app.core.dependencies import get_execution_progress_runtime

        progress = get_execution_progress_runtime().create_progress(
            _summary(completed=("a",))
        )
        self.assertIsInstance(progress, ExecutionProgress)
        self.assertEqual(progress.progress_status, "COMPLETED")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import ExecutionProgressRuntimeDep

        self.assertIsNotNone(ExecutionProgressRuntimeDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_capability_dispatcher
        from app.services.runtime.capability_dispatcher import (
            CapabilityDispatcher,
        )

        self.assertIsInstance(get_capability_dispatcher(), CapabilityDispatcher)


# =====================================================================
# Regression: Sprint 14.5 executor & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_executor_seam_still_raises(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
