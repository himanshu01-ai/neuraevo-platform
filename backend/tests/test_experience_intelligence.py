"""Unit + integration tests for the Sprint 16.12 Experience Intelligence Platform.

Exercises the experience-intelligence subsystem: the :class:`FeedbackManager`, the
:class:`ExperienceAnalyzer`, the :class:`BehaviorAnalyzer`, the
:class:`QualityEvaluator`, the :class:`FrictionDetector`, the
:class:`RecommendationEngine`, the :class:`ImprovementReporter`, and the
:class:`ExperienceIntelligenceManager` that coordinates them over the frozen Sprint
16.10 :class:`AIEmployeeService`.

The Experience Intelligence Platform observes only — it never plans, never executes a
workflow, and never modifies AI behaviour. Every business request is delegated to the
:class:`AIEmployeeService` (which here runs over deterministic recording doubles), and
the platform connects to no machine-learning model, prediction engine, prompt
optimiser, LLM evaluator, cloud analytics service, telemetry SDK, HTTP transport, or
database.

Covers, as the sprint requires: feedback, experience metrics, behaviour analytics,
quality evaluation, friction detection, recommendation generation, reports, platform
summary, DTO immutability, DI wiring, and regression (Sprints 16.1–16.11 unchanged;
the experience sub-package imports no Workflow Coordinator, capability, repository, LLM
provider, database, HTTP, ML, or analytics facility).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_experience_intelligence
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import AIEmployee, EmployeeProfile
from app.services.ai_employee.experience import (
    BehaviorAnalyzer,
    BehaviorMetrics,
    ExperienceAnalyzer,
    ExperienceGrade,
    ExperienceIntelligenceManager,
    ExperienceMetrics,
    FeedbackCategory,
    FeedbackManager,
    FeedbackRecord,
    FrictionDetector,
    FrictionPoint,
    FrictionReport,
    FrictionSeverity,
    FrictionType,
    ImprovementRecommendation,
    ImprovementReporter,
    ImprovementReport,
    PlatformExperienceSummary,
    QualityAssessment,
    QualityEvaluator,
    RecommendationCategory,
    RecommendationEngine,
    RecommendationPriority,
    ReportPeriod,
)
from app.services.ai_employee.service import (
    AIEmployeeService,
    ErrorMapper,
    HealthManager,
    IdempotencyManager,
    RequestValidator,
    ResponseBuilder,
    SessionManager,
    TaskState,
    TaskStatusResponse,
    TaskSubmissionRequest,
)
from app.services.ai_employee.service.health import HEALTH_COMPONENTS
from app.services.planning.models import ExecutionPlan
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

_COMPLETED = WorkflowStatus.COMPLETED.value


# =====================================================================
# Offline recording doubles + helpers
# =====================================================================
class _RecordingPlanningEngine:
    def create_plan(self, request) -> ExecutionPlan:
        return ExecutionPlan(goal="g", summary="s")


class _RecordingWorkflowCoordinator:
    def __init__(self, status: str = _COMPLETED) -> None:
        self._status = status

    def execute(
        self,
        steps,
        workflow_id="workflow",
        runtime_id="",
        execution_id="",
        initial_inputs=None,
    ) -> WorkflowExecutionResult:
        return WorkflowExecutionResult(
            workflow_id=workflow_id,
            workflow_status=self._status,
            total_step_count=len(steps),
        )


def _service(status: str = _COMPLETED) -> AIEmployeeService:
    ai = AIEmployee(
        _RecordingPlanningEngine(), _RecordingWorkflowCoordinator(status)
    )
    return AIEmployeeService(
        ai,
        SessionManager(),
        RequestValidator(),
        ResponseBuilder(),
        IdempotencyManager(),
        HealthManager({name: True for name in HEALTH_COMPONENTS}),
        ErrorMapper(),
    )


def _manager(status: str = _COMPLETED) -> ExperienceIntelligenceManager:
    service = _service(status)
    return ExperienceIntelligenceManager(
        FeedbackManager(),
        ExperienceAnalyzer(service),
        BehaviorAnalyzer(service),
        QualityEvaluator(service),
        FrictionDetector(service),
        RecommendationEngine(),
        ImprovementReporter(),
        service,
    )


def _request(request_id="r1", task_id="biz-1"):
    return TaskSubmissionRequest(
        request_id=request_id,
        employee=EmployeeProfile(employee_id="e1", name="Ada"),
        task_id=task_id,
        task="write the report",
        workflow_steps=[WorkflowStep(step_id="s1", capability_name="demo")],
    )


def _task(
    task_id="t1",
    state=TaskState.COMPLETED,
    success=True,
    **summary,
) -> TaskStatusResponse:
    """Build an observed task carrying explicit experience-signal descriptors."""
    return TaskStatusResponse(
        task_id=task_id,
        state=state,
        success=success,
        result_summary=dict(summary),
    )


# =====================================================================
# Feedback
# =====================================================================
class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.feedback = FeedbackManager()

    def test_submit_appends_immutable_record(self):
        record = self.feedback.submit(
            rating=5, comment="great", category=FeedbackCategory.FEATURE
        )
        self.assertIsInstance(record, FeedbackRecord)
        self.assertEqual(record.rating, 5)
        self.assertEqual(record.category, FeedbackCategory.FEATURE)
        self.assertEqual(len(self.feedback.history()), 1)

    def test_sequence_is_monotonic(self):
        first = self.feedback.submit(rating=3)
        second = self.feedback.submit(rating=4)
        self.assertEqual(second.sequence, first.sequence + 1)

    def test_history_is_a_copy(self):
        self.feedback.submit(rating=3)
        history = self.feedback.history()
        history.clear()
        self.assertEqual(len(self.feedback.history()), 1)

    def test_summary_counts_and_average(self):
        self.feedback.submit(rating=5, category=FeedbackCategory.FEATURE)
        self.feedback.submit(rating=3, category=FeedbackCategory.FEATURE)
        self.feedback.submit(rating=4, category=FeedbackCategory.WORKFLOW)
        summary = self.feedback.summary()
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["average_rating"], 4.0)
        self.assertEqual(summary["by_category"]["FEATURE"], 2)
        self.assertEqual(summary["by_rating"][5], 1)

    def test_empty_summary(self):
        summary = self.feedback.summary()
        self.assertEqual(summary["count"], 0)
        self.assertEqual(summary["average_rating"], 0.0)

    def test_rating_is_bounded(self):
        with self.assertRaises(ValidationError):
            self.feedback.submit(rating=6)
        with self.assertRaises(ValidationError):
            self.feedback.submit(rating=0)


# =====================================================================
# Experience metrics
# =====================================================================
class ExperienceMetricsTests(unittest.TestCase):
    def test_empty_is_all_zero(self):
        metrics = ExperienceAnalyzer(_service()).analyze([])
        self.assertIsInstance(metrics, ExperienceMetrics)
        self.assertEqual(metrics.task_count, 0)
        self.assertEqual(metrics.task_success_rate, 0.0)

    def test_success_and_completion_rates(self):
        tasks = [
            _task("t1", workflow_status="COMPLETED", executed_step_count=2),
            _task(
                "t2",
                state=TaskState.FAILED,
                success=False,
                workflow_status="FAILED",
                executed_step_count=4,
            ),
        ]
        metrics = ExperienceAnalyzer(_service()).analyze(tasks)
        self.assertEqual(metrics.task_count, 2)
        self.assertEqual(metrics.task_success_rate, 0.5)
        self.assertEqual(metrics.workflow_completion_rate, 0.5)
        self.assertEqual(metrics.average_execution_units, 3.0)

    def test_approval_and_recovery_rates(self):
        tasks = [
            _task("t1", approval_required=True, recovery_required=False),
            _task("t2", approval_required=False, recovery_required=True),
            _task("t3"),
            _task("t4"),
        ]
        metrics = ExperienceAnalyzer(_service()).analyze(tasks)
        self.assertEqual(metrics.approval_rate, 0.25)
        self.assertEqual(metrics.recovery_rate, 0.25)

    def test_capability_success(self):
        tasks = [
            _task("t1", capability="browser", success=True),
            _task(
                "t2",
                capability="browser",
                state=TaskState.FAILED,
                success=False,
            ),
            _task("t3", capability="email", success=True),
        ]
        metrics = ExperienceAnalyzer(_service()).analyze(tasks)
        self.assertEqual(metrics.capability_success["browser"], 0.5)
        self.assertEqual(metrics.capability_success["email"], 1.0)

    def test_reads_live_service_tasks(self):
        service = _service()
        service.submit_task(_request(task_id="b1"))
        service.submit_task(_request(request_id="r2", task_id="b2"))
        metrics = ExperienceAnalyzer(service).analyze()
        self.assertEqual(metrics.task_count, 2)
        self.assertEqual(metrics.task_success_rate, 1.0)


# =====================================================================
# Behavior analytics
# =====================================================================
class BehaviorAnalyticsTests(unittest.TestCase):
    def test_usage_counts(self):
        tasks = [
            _task("t1", capability="browser", feature="search", workflow="wf"),
            _task("t2", capability="browser", feature="search", workflow="wf"),
            _task("t3", capability="email", feature="compose", workflow="wf2"),
        ]
        metrics = BehaviorAnalyzer(_service()).analyze(tasks)
        self.assertIsInstance(metrics, BehaviorMetrics)
        self.assertEqual(metrics.capability_usage["browser"], 2)
        self.assertEqual(metrics.feature_usage["search"], 2)
        self.assertEqual(metrics.workflow_frequency["wf"], 2)

    def test_repeat_usage_is_over_used_capabilities(self):
        tasks = [
            _task("t1", capability="browser"),
            _task("t2", capability="browser"),
            _task("t3", capability="email"),
        ]
        metrics = BehaviorAnalyzer(_service()).analyze(tasks)
        self.assertEqual(metrics.repeat_usage, {"browser": 2})

    def test_session_analytics_from_service(self):
        service = _service()
        service.submit_task(_request(task_id="b1"))
        metrics = BehaviorAnalyzer(service).analyze()
        self.assertEqual(metrics.total_sessions, 1)

    def test_empty(self):
        metrics = BehaviorAnalyzer(_service()).analyze([])
        self.assertEqual(metrics.capability_usage, {})
        self.assertEqual(metrics.repeat_usage, {})


# =====================================================================
# Quality evaluation
# =====================================================================
class QualityEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = QualityEvaluator(_service())

    def test_perfect_task_scores_100(self):
        assessment = self.evaluator.evaluate(
            _task("t1", goal_achieved=True, output_accepted=True)
        )
        self.assertIsInstance(assessment, QualityAssessment)
        self.assertTrue(assessment.goal_achieved)
        self.assertEqual(assessment.quality_score, 100.0)

    def test_missed_goal_penalised(self):
        assessment = self.evaluator.evaluate(
            _task(
                "t1",
                state=TaskState.FAILED,
                success=False,
                goal_achieved=False,
                output_accepted=True,
            )
        )
        self.assertFalse(assessment.goal_achieved)
        self.assertEqual(assessment.quality_score, 50.0)

    def test_retry_and_recovery_penalties(self):
        assessment = self.evaluator.evaluate(
            _task(
                "t1",
                goal_achieved=True,
                output_accepted=True,
                retry_count=2,
                recovery_required=True,
            )
        )
        # 100 - (2 * 10) - 15 = 65
        self.assertEqual(assessment.retry_count, 2)
        self.assertEqual(assessment.quality_score, 65.0)

    def test_goal_defaults_to_success(self):
        assessment = self.evaluator.evaluate(_task("t1", success=True))
        self.assertTrue(assessment.goal_achieved)
        self.assertTrue(assessment.output_accepted)

    def test_score_never_negative(self):
        assessment = self.evaluator.evaluate(
            _task(
                "t1",
                state=TaskState.FAILED,
                success=False,
                goal_achieved=False,
                output_accepted=False,
                retry_count=10,
            )
        )
        self.assertGreaterEqual(assessment.quality_score, 0.0)

    def test_aggregate(self):
        tasks = [
            _task("t1", goal_achieved=True, output_accepted=True),
            _task(
                "t2",
                state=TaskState.FAILED,
                success=False,
                goal_achieved=False,
                output_accepted=True,
                recovery_required=True,
            ),
        ]
        aggregate = self.evaluator.aggregate(tasks)
        self.assertEqual(aggregate.task_id, "__platform__")
        self.assertFalse(aggregate.goal_achieved)  # not all achieved
        self.assertTrue(aggregate.recovery_required)  # any required
        # scores 100 and 35 -> mean 67.5
        self.assertEqual(aggregate.quality_score, 67.5)

    def test_aggregate_empty(self):
        aggregate = self.evaluator.aggregate([])
        self.assertEqual(aggregate.quality_score, 0.0)


# =====================================================================
# Friction detection
# =====================================================================
class FrictionDetectionTests(unittest.TestCase):
    def setUp(self):
        self.detector = FrictionDetector(_service())

    def test_no_tasks_no_friction(self):
        report = self.detector.detect([])
        self.assertIsInstance(report, FrictionReport)
        self.assertFalse(report.friction_detected)

    def test_frequent_failures_high(self):
        tasks = [
            _task("t1", state=TaskState.FAILED, success=False),
            _task("t2", state=TaskState.FAILED, success=False),
            _task("t3", success=True),
            _task("t4", success=True),
        ]
        report = self.detector.detect(tasks)
        self.assertTrue(report.friction_detected)
        types = {p.friction_type for p in report.points}
        self.assertIn(FrictionType.FREQUENT_FAILURES, types)
        self.assertEqual(report.highest_severity, FrictionSeverity.HIGH)

    def test_repeated_retries(self):
        tasks = [
            _task("t1", retry_count=2),
            _task("t2", retry_count=1),
            _task("t3"),
            _task("t4"),
        ]
        report = self.detector.detect(tasks)
        types = {p.friction_type for p in report.points}
        self.assertIn(FrictionType.REPEATED_RETRIES, types)

    def test_long_workflows(self):
        tasks = [
            _task("t1", executed_step_count=12),
            _task("t2", executed_step_count=10),
            _task("t3", executed_step_count=1),
            _task("t4", executed_step_count=1),
        ]
        report = self.detector.detect(tasks)
        types = {p.friction_type for p in report.points}
        self.assertIn(FrictionType.LONG_WORKFLOWS, types)

    def test_high_cancellation(self):
        tasks = [
            _task("t1", state=TaskState.CANCELLED, success=False),
            _task("t2", state=TaskState.CANCELLED, success=False),
            _task("t3", success=True),
            _task("t4", success=True),
        ]
        report = self.detector.detect(tasks)
        types = {p.friction_type for p in report.points}
        self.assertIn(FrictionType.HIGH_CANCELLATION, types)

    def test_abandoned_tasks(self):
        tasks = [
            _task("t1", state=TaskState.PAUSED, success=False),
            _task("t2", success=True),
            _task("t3", success=True),
            _task("t4", success=True),
        ]
        report = self.detector.detect(tasks)
        types = {p.friction_type for p in report.points}
        self.assertIn(FrictionType.ABANDONED_TASKS, types)


# =====================================================================
# Recommendation generation (deterministic, rule-based)
# =====================================================================
class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.engine = RecommendationEngine()

    def _experience(self, **kwargs):
        base = dict(
            task_count=4,
            task_success_rate=1.0,
            workflow_completion_rate=1.0,
            approval_rate=0.0,
            recovery_rate=0.0,
            capability_success={},
        )
        base.update(kwargs)
        return ExperienceMetrics(**base)

    def test_low_capability_recommends_improvement(self):
        experience = self._experience(
            capability_success={"browser": 0.4}
        )
        recs = self.engine.recommend(
            experience,
            BehaviorMetrics(),
            FrictionReport(),
            QualityAssessment(task_id="__platform__", quality_score=100.0),
        )
        titles = [r.title for r in recs]
        self.assertIn("Improve browser capability", titles)
        browser = next(r for r in recs if r.target == "browser")
        self.assertEqual(browser.category, RecommendationCategory.CAPABILITY)

    def test_long_workflow_friction_recommends_reduction(self):
        friction = FrictionReport(
            friction_detected=True,
            points=[
                FrictionPoint(
                    friction_type=FrictionType.LONG_WORKFLOWS,
                    severity=FrictionSeverity.MEDIUM,
                    detail="long",
                )
            ],
            highest_severity=FrictionSeverity.MEDIUM,
        )
        recs = self.engine.recommend(
            self._experience(),
            BehaviorMetrics(),
            friction,
            QualityAssessment(quality_score=100.0),
        )
        titles = [r.title for r in recs]
        self.assertIn("Reduce workflow length", titles)

    def test_high_approval_and_recovery(self):
        experience = self._experience(approval_rate=0.8, recovery_rate=0.5)
        recs = self.engine.recommend(
            experience,
            BehaviorMetrics(),
            FrictionReport(),
            QualityAssessment(quality_score=100.0),
        )
        titles = [r.title for r in recs]
        self.assertIn("Optimize approval flow", titles)
        self.assertIn("Improve recovery", titles)

    def test_no_signals_no_recommendations(self):
        recs = self.engine.recommend(
            ExperienceMetrics(task_count=0),
            BehaviorMetrics(),
            FrictionReport(),
            QualityAssessment(quality_score=100.0),
        )
        self.assertEqual(recs, [])

    def test_deterministic_and_ordered(self):
        experience = self._experience(
            task_success_rate=0.5,
            capability_success={"browser": 0.1},
        )
        friction = FrictionReport(
            friction_detected=True,
            points=[
                FrictionPoint(
                    friction_type=FrictionType.HIGH_CANCELLATION,
                    severity=FrictionSeverity.LOW,
                    detail="c",
                )
            ],
            highest_severity=FrictionSeverity.LOW,
        )
        quality = QualityAssessment(quality_score=40.0)
        first = self.engine.recommend(
            experience, BehaviorMetrics(), friction, quality
        )
        second = self.engine.recommend(
            experience, BehaviorMetrics(), friction, quality
        )
        self.assertEqual(
            [r.recommendation_id for r in first],
            [r.recommendation_id for r in second],
        )
        # High priority first.
        priorities = [r.priority for r in first]
        self.assertEqual(priorities[0], RecommendationPriority.HIGH)
        self.assertTrue(
            all(isinstance(r, ImprovementRecommendation) for r in first)
        )


# =====================================================================
# Reports
# =====================================================================
class ReportTests(unittest.TestCase):
    def setUp(self):
        self.reporter = ImprovementReporter()
        self.experience = ExperienceMetrics(
            task_count=3,
            task_success_rate=1.0,
            workflow_completion_rate=1.0,
            capability_success={"browser": 1.0},
        )
        self.behavior = BehaviorMetrics(total_sessions=3)
        self.friction = FrictionReport(summary="no friction")

    def test_daily_report(self):
        report = self.reporter.daily_report(
            self.experience, self.behavior, self.friction
        )
        self.assertIsInstance(report, ImprovementReport)
        self.assertEqual(report.period, ReportPeriod.DAILY)
        self.assertEqual(report.report_id, "report-daily")
        self.assertTrue(report.highlights)

    def test_weekly_and_platform_reports(self):
        weekly = self.reporter.weekly_report(
            self.experience, self.behavior, self.friction
        )
        platform = self.reporter.platform_report(
            self.experience, self.behavior, self.friction
        )
        self.assertEqual(weekly.period, ReportPeriod.WEEKLY)
        self.assertEqual(platform.period, ReportPeriod.PLATFORM)

    def test_capability_report(self):
        report = self.reporter.capability_report(self.experience)
        self.assertEqual(report.period, ReportPeriod.CAPABILITY)
        self.assertIn("browser: 100% success", report.highlights)

    def test_experience_summary_grade(self):
        summary = self.reporter.experience_summary(
            self.experience,
            self.behavior,
            self.friction,
            QualityAssessment(quality_score=100.0),
            feedback_summary={"count": 2, "average_rating": 4.5},
            recommendation_count=0,
        )
        self.assertIsInstance(summary, PlatformExperienceSummary)
        self.assertEqual(summary.grade, ExperienceGrade.EXCELLENT)
        self.assertEqual(summary.feedback_count, 2)
        self.assertEqual(summary.average_rating, 4.5)

    def test_high_friction_caps_grade(self):
        friction = FrictionReport(
            friction_detected=True,
            highest_severity=FrictionSeverity.HIGH,
            points=[
                FrictionPoint(
                    friction_type=FrictionType.FREQUENT_FAILURES,
                    severity=FrictionSeverity.HIGH,
                )
            ],
        )
        summary = self.reporter.experience_summary(
            self.experience,
            self.behavior,
            friction,
            QualityAssessment(quality_score=100.0),
        )
        # Blended would be EXCELLENT, but HIGH friction caps it at FAIR.
        self.assertEqual(summary.grade, ExperienceGrade.FAIR)

    def test_empty_platform_is_fair(self):
        summary = self.reporter.experience_summary(
            ExperienceMetrics(task_count=0),
            BehaviorMetrics(),
            FrictionReport(),
            QualityAssessment(),
        )
        self.assertEqual(summary.grade, ExperienceGrade.FAIR)


# =====================================================================
# Platform summary + manager coordination
# =====================================================================
class ManagerTests(unittest.TestCase):
    def test_record_feedback_delegates(self):
        manager = _manager()
        record = manager.record_feedback(
            rating=5, category=FeedbackCategory.EXPERIENCE
        )
        self.assertIsInstance(record, FeedbackRecord)
        self.assertEqual(len(manager.feedback_history()), 1)

    def test_analyze_returns_summary(self):
        manager = _manager()
        manager.submit_task(_request(task_id="b1"))
        manager.submit_task(_request(request_id="r2", task_id="b2"))
        summary = manager.analyze()
        self.assertIsInstance(summary, PlatformExperienceSummary)
        self.assertEqual(summary.experience.task_count, 2)
        self.assertEqual(summary.experience.task_success_rate, 1.0)

    def test_platform_summary_matches_analyze(self):
        manager = _manager()
        manager.submit_task(_request())
        self.assertEqual(
            manager.analyze().experience.task_count,
            manager.platform_summary().experience.task_count,
        )

    def test_recommendations(self):
        manager = _manager(status=WorkflowStatus.FAILED.value)
        manager.submit_task(_request(task_id="b1"))
        manager.submit_task(_request(request_id="r2", task_id="b2"))
        recs = manager.recommendations()
        self.assertTrue(
            all(isinstance(r, ImprovementRecommendation) for r in recs)
        )
        # Failing tasks drive a reliability/failure recommendation.
        self.assertTrue(recs)

    def test_report_periods(self):
        manager = _manager()
        manager.submit_task(_request())
        self.assertEqual(
            manager.report(ReportPeriod.DAILY).period, ReportPeriod.DAILY
        )
        self.assertEqual(
            manager.report(ReportPeriod.WEEKLY).period, ReportPeriod.WEEKLY
        )
        self.assertEqual(
            manager.report(ReportPeriod.PLATFORM).period,
            ReportPeriod.PLATFORM,
        )
        self.assertEqual(
            manager.report(ReportPeriod.CAPABILITY).period,
            ReportPeriod.CAPABILITY,
        )

    def test_submit_task_delegates_to_service(self):
        manager = _manager()
        response = manager.submit_task(_request())
        self.assertTrue(response.accepted)
        self.assertEqual(len(manager.service.list_tasks()), 1)

    def test_recommendation_count_matches(self):
        manager = _manager(status=WorkflowStatus.FAILED.value)
        manager.submit_task(_request())
        summary = manager.platform_summary()
        self.assertEqual(
            summary.recommendation_count, len(manager.recommendations())
        )

    def test_manager_holds_only_declared_collaborators(self):
        manager = _manager()
        self.assertEqual(
            set(vars(manager)),
            {
                "feedback",
                "experience_analyzer",
                "behavior_analyzer",
                "quality_evaluator",
                "friction_detector",
                "recommendation_engine",
                "reporter",
                "service",
            },
        )


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def test_feedback_record_is_frozen(self):
        record = FeedbackRecord(feedback_id="f1", rating=5)
        with self.assertRaises(ValidationError):
            record.rating = 1

    def test_metrics_are_frozen(self):
        with self.assertRaises(ValidationError):
            ExperienceMetrics().task_count = 3
        with self.assertRaises(ValidationError):
            BehaviorMetrics().total_sessions = 1

    def test_quality_assessment_is_frozen(self):
        with self.assertRaises(ValidationError):
            QualityAssessment().quality_score = 50.0

    def test_friction_dtos_are_frozen(self):
        with self.assertRaises(ValidationError):
            FrictionReport().friction_detected = True
        with self.assertRaises(ValidationError):
            FrictionPoint(
                friction_type=FrictionType.LONG_WORKFLOWS,
                severity=FrictionSeverity.LOW,
            ).metric = 1.0

    def test_recommendation_and_report_frozen(self):
        with self.assertRaises(ValidationError):
            ImprovementRecommendation(
                recommendation_id="r1",
                category=RecommendationCategory.QUALITY,
                priority=RecommendationPriority.LOW,
                title="t",
            ).title = "x"
        with self.assertRaises(ValidationError):
            ImprovementReport(
                report_id="rep-1", period=ReportPeriod.DAILY
            ).period = ReportPeriod.WEEKLY

    def test_summary_is_frozen(self):
        summary = PlatformExperienceSummary(
            grade=ExperienceGrade.GOOD,
            experience=ExperienceMetrics(),
            behavior=BehaviorMetrics(),
            friction=FrictionReport(),
            quality=QualityAssessment(),
        )
        with self.assertRaises(ValidationError):
            summary.grade = ExperienceGrade.POOR

    def test_quality_score_bounds(self):
        with self.assertRaises(ValidationError):
            QualityAssessment(quality_score=150.0)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_behavior_analyzer,
            get_experience_analyzer,
            get_feedback_manager,
            get_friction_detector,
            get_improvement_reporter,
            get_quality_evaluator,
            get_recommendation_engine,
        )

        self.assertIsInstance(get_feedback_manager(), FeedbackManager)
        self.assertIsInstance(
            get_experience_analyzer(), ExperienceAnalyzer
        )
        self.assertIsInstance(get_behavior_analyzer(), BehaviorAnalyzer)
        self.assertIsInstance(get_quality_evaluator(), QualityEvaluator)
        self.assertIsInstance(get_friction_detector(), FrictionDetector)
        self.assertIsInstance(
            get_recommendation_engine(), RecommendationEngine
        )
        self.assertIsInstance(
            get_improvement_reporter(), ImprovementReporter
        )

    def test_manager_provider_wires_collaborators(self):
        from app.core.dependencies import (
            get_experience_intelligence_manager,
        )

        manager = get_experience_intelligence_manager()
        self.assertIsInstance(manager, ExperienceIntelligenceManager)
        self.assertIsInstance(manager.feedback, FeedbackManager)
        self.assertIsInstance(
            manager.experience_analyzer, ExperienceAnalyzer
        )
        self.assertIsInstance(manager.behavior_analyzer, BehaviorAnalyzer)
        self.assertIsInstance(manager.quality_evaluator, QualityEvaluator)
        self.assertIsInstance(manager.friction_detector, FrictionDetector)
        self.assertIsInstance(
            manager.recommendation_engine, RecommendationEngine
        )
        self.assertIsInstance(manager.reporter, ImprovementReporter)
        self.assertIsInstance(manager.service, AIEmployeeService)

    def test_manager_provider_shares_service(self):
        from app.core.dependencies import (
            get_experience_intelligence_manager,
        )

        manager = get_experience_intelligence_manager()
        # Every analyzer must observe the same platform state.
        self.assertIs(manager.service, manager.experience_analyzer.service)
        self.assertIs(manager.service, manager.behavior_analyzer.service)
        self.assertIs(manager.service, manager.friction_detector.service)

    def test_manager_provider_uses_injected(self):
        from app.core.dependencies import (
            get_experience_intelligence_manager,
        )

        feedback = FeedbackManager()
        manager = get_experience_intelligence_manager(feedback=feedback)
        self.assertIs(manager.feedback, feedback)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            BehaviorAnalyzerDep,
            ExperienceAnalyzerDep,
            ExperienceIntelligenceManagerDep,
            FeedbackManagerDep,
            FrictionDetectorDep,
            ImprovementReporterDep,
            QualityEvaluatorDep,
            RecommendationEngineDep,
        )

        for dep in (
            FeedbackManagerDep,
            ExperienceAnalyzerDep,
            BehaviorAnalyzerDep,
            QualityEvaluatorDep,
            FrictionDetectorDep,
            RecommendationEngineDep,
            ImprovementReporterDep,
            ExperienceIntelligenceManagerDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: prior sprints frozen; no forbidden imports
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_MODULES = {
        "workflow_coordinator",
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
        "repository",
        "fastapi",
        "starlette",
        "sqlalchemy",
        "database",
        "threading",
        "asyncio",
        "socket",
        "requests",
        "httpx",
        "anthropic",
        "openai",
        "boto3",
        "prometheus_client",
        # Sprint 16.12 non-goals: no ML / prediction / analytics.
        "sklearn",
        "tensorflow",
        "torch",
        "numpy",
        "pandas",
    }

    def test_frozen_1611_operations_unchanged(self):
        from app.core.dependencies import (
            get_enterprise_operations_manager,
        )
        from app.services.ai_employee.operations import (
            EnterpriseOperationsManager,
        )

        self.assertIsInstance(
            get_enterprise_operations_manager(), EnterpriseOperationsManager
        )

    def test_frozen_1610_service_unchanged(self):
        from app.core.dependencies import get_ai_employee_service

        self.assertIsInstance(
            get_ai_employee_service(), AIEmployeeService
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_experience_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.experience as pkg

        package_dir = os.path.dirname(pkg.__file__)
        offenders = []
        for filename in os.listdir(package_dir):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(package_dir, filename)
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                elif isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                for name in names:
                    tail = name.rsplit(".", 1)[-1]
                    if tail in self._FORBIDDEN_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
