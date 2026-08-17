"""Unit + integration tests for the Sprint 16.6 Memory Orchestrator.

Exercises the memory subsystem: the configurable :class:`RuleBasedMemoryPolicy`
(decide what to remember), the configurable :class:`RuleBasedMemoryClassifier`
(importance), the deterministic in-memory :class:`MemoryRetriever` (exact-match
retrieval — no embeddings or semantic search), and the :class:`MemoryOrchestrator`
that coordinates them and routes durable workflow-state storage through the frozen
Sprint 16.5 :class:`PersistenceManager`. Everything is deterministic and in-memory.

Covers, as the sprint requires: remember, recall, forget, update, summarize,
classification, policy, retrieval, persistence integration, DTO immutability, DI
wiring, and regression (Sprints 16.1–16.5 unchanged; the older semantic-memory
services still work; the memory sub-package imports no capability, vector store, or
embedding module).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_memory_orchestrator
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    EmployeeProfile,
    TaskDelegation,
    WorkflowLifecycleStatus,
)
from app.services.ai_employee.memory import (
    MemoryCategory,
    MemoryClassifier,
    MemoryDecision,
    MemoryImportance,
    MemoryNotFoundError,
    MemoryOrchestrator,
    MemoryPolicy,
    MemoryQuery,
    MemoryRecord,
    MemoryRetriever,
    MemorySummary,
    RuleBasedMemoryClassifier,
    RuleBasedMemoryPolicy,
)
from app.services.ai_employee.persistence import (
    InMemoryPersistenceRepository,
    PersistenceManager,
)
from app.services.runtime.workflow_models import WorkflowStep

C = MemoryCategory
I = MemoryImportance


# =====================================================================
# Helpers
# =====================================================================
def _persistence():
    return PersistenceManager(InMemoryPersistenceRepository())


def _orchestrator(policy=None, classifier=None):
    return MemoryOrchestrator(
        policy or RuleBasedMemoryPolicy(),
        classifier or RuleBasedMemoryClassifier(),
        MemoryRetriever(),
        _persistence(),
    )


def _instance(task_id="t1"):
    from app.core.dependencies import get_workflow_lifecycle_manager

    return get_workflow_lifecycle_manager().create_instance(
        EmployeeProfile(employee_id="e1", name="Ada"),
        TaskDelegation(task_id=task_id, task="do it"),
        [WorkflowStep(step_id="s1", capability_name="demo")],
    )


def _record(memory_id, category=C.WORKFLOW, importance=I.LONG_TERM,
            workflow_id="wf1", tags=None, sequence=0):
    return MemoryRecord(
        memory_id=memory_id,
        workflow_id=workflow_id,
        category=category,
        importance=importance,
        tags=tags or [],
        created_at_sequence=sequence,
    )


# =====================================================================
# Policy
# =====================================================================
class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = RuleBasedMemoryPolicy()

    def test_is_a_memory_policy(self):
        self.assertIsInstance(self.policy, MemoryPolicy)

    def test_default_remembers_most_categories(self):
        for category in (
            C.USER_PREFERENCE, C.WORKFLOW, C.TASK_RESULT, C.APPROVAL, C.SYSTEM
        ):
            self.assertTrue(self.policy.should_remember(category))

    def test_default_skips_transient_notifications(self):
        self.assertFalse(self.policy.should_remember(C.NOTIFICATION))

    def test_policy_is_configurable(self):
        policy = RuleBasedMemoryPolicy(rememberable={C.NOTIFICATION})
        self.assertTrue(policy.should_remember(C.NOTIFICATION))
        self.assertFalse(policy.should_remember(C.USER_PREFERENCE))


# =====================================================================
# Classifier
# =====================================================================
class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = RuleBasedMemoryClassifier()

    def test_is_a_memory_classifier(self):
        self.assertIsInstance(self.classifier, MemoryClassifier)

    def test_default_mapping(self):
        self.assertEqual(self.classifier.classify(C.USER_PREFERENCE), I.PERMANENT)
        self.assertEqual(self.classifier.classify(C.SYSTEM), I.PERMANENT)
        self.assertEqual(self.classifier.classify(C.WORKFLOW), I.LONG_TERM)
        self.assertEqual(self.classifier.classify(C.TASK_RESULT), I.LONG_TERM)
        self.assertEqual(self.classifier.classify(C.APPROVAL), I.SHORT_TERM)
        self.assertEqual(self.classifier.classify(C.NOTIFICATION), I.TEMPORARY)

    def test_classifier_is_configurable(self):
        classifier = RuleBasedMemoryClassifier(
            mapping={C.APPROVAL: I.PERMANENT}
        )
        self.assertEqual(classifier.classify(C.APPROVAL), I.PERMANENT)

    def test_classification_is_deterministic(self):
        self.assertEqual(
            self.classifier.classify(C.WORKFLOW),
            self.classifier.classify(C.WORKFLOW),
        )


# =====================================================================
# Retriever
# =====================================================================
class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.retriever = MemoryRetriever()
        self.a = _record("m1", C.WORKFLOW, I.LONG_TERM, "wf1", ["x"], 1)
        self.b = _record("m2", C.APPROVAL, I.SHORT_TERM, "wf1", ["y"], 2)
        self.c = _record("m3", C.WORKFLOW, I.LONG_TERM, "wf2", ["x"], 3)
        for record in (self.a, self.b, self.c):
            self.retriever.add(record)

    def test_add_get_all_preserve_order(self):
        self.assertEqual(self.retriever.get("m2"), self.b)
        self.assertEqual(
            [r.memory_id for r in self.retriever.all()], ["m1", "m2", "m3"]
        )

    def test_remove(self):
        self.assertTrue(self.retriever.remove("m2"))
        self.assertFalse(self.retriever.remove("m2"))
        self.assertIsNone(self.retriever.get("m2"))

    def test_retrieve_by_workflow(self):
        found = self.retriever.retrieve(MemoryQuery(workflow_id="wf1"))
        self.assertEqual([r.memory_id for r in found], ["m1", "m2"])

    def test_retrieve_by_category(self):
        found = self.retriever.retrieve(MemoryQuery(category=C.WORKFLOW))
        self.assertEqual([r.memory_id for r in found], ["m1", "m3"])

    def test_retrieve_by_priority(self):
        found = self.retriever.retrieve(MemoryQuery(importance=I.SHORT_TERM))
        self.assertEqual([r.memory_id for r in found], ["m2"])

    def test_retrieve_by_tag(self):
        found = self.retriever.retrieve(MemoryQuery(tag="x"))
        self.assertEqual([r.memory_id for r in found], ["m1", "m3"])

    def test_retrieve_latest_and_limit(self):
        found = self.retriever.retrieve(MemoryQuery(latest=True, limit=2))
        self.assertEqual([r.memory_id for r in found], ["m3", "m2"])


# =====================================================================
# Decide / remember
# =====================================================================
class RememberTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = _orchestrator()

    def test_decide_returns_decision(self):
        decision = self.orchestrator.decide(C.USER_PREFERENCE, "dark mode")
        self.assertIsInstance(decision, MemoryDecision)
        self.assertTrue(decision.should_remember)
        self.assertEqual(decision.importance, I.PERMANENT)

    def test_decide_skips_notification(self):
        decision = self.orchestrator.decide(C.NOTIFICATION, "noise")
        self.assertFalse(decision.should_remember)

    def test_remember_stores_a_record(self):
        record = self.orchestrator.remember(
            C.USER_PREFERENCE, "dark mode", tags=["ui"]
        )
        self.assertIsInstance(record, MemoryRecord)
        self.assertEqual(record.importance, I.PERMANENT)
        self.assertEqual(record.tags, ["ui"])
        self.assertEqual(record.category, C.USER_PREFERENCE)

    def test_remember_declined_returns_none(self):
        self.assertIsNone(self.orchestrator.remember(C.NOTIFICATION, "noise"))
        self.assertEqual(len(self.orchestrator.recall(MemoryQuery())), 0)

    def test_remember_ids_are_deterministic(self):
        a = _orchestrator().remember(C.SYSTEM, "k")
        b = _orchestrator().remember(C.SYSTEM, "k")
        self.assertEqual(a.memory_id, b.memory_id)

    def test_orchestrator_holds_only_its_collaborators(self):
        # No direct store, repository, or database on the orchestrator.
        self.assertEqual(
            set(vars(self.orchestrator)),
            {"policy", "classifier", "retriever", "persistence", "_sequence"},
        )


# =====================================================================
# Recall
# =====================================================================
class RecallTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = _orchestrator()
        self.orchestrator.remember(C.USER_PREFERENCE, "a", tags=["ui"])
        self.orchestrator.remember(C.SYSTEM, "b")
        self.orchestrator.remember(C.APPROVAL, "c", workflow_id="wf9")

    def test_recall_all(self):
        self.assertEqual(len(self.orchestrator.recall(MemoryQuery())), 3)

    def test_recall_by_category(self):
        found = self.orchestrator.recall(MemoryQuery(category=C.SYSTEM))
        self.assertEqual([r.content for r in found], ["b"])

    def test_recall_by_importance(self):
        found = self.orchestrator.recall(MemoryQuery(importance=I.PERMANENT))
        self.assertEqual({r.content for r in found}, {"a", "b"})

    def test_recall_by_tag(self):
        found = self.orchestrator.recall(MemoryQuery(tag="ui"))
        self.assertEqual([r.content for r in found], ["a"])


# =====================================================================
# Forget / update
# =====================================================================
class ForgetUpdateTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = _orchestrator()
        self.record = self.orchestrator.remember(
            C.USER_PREFERENCE, "dark mode", tags=["ui"]
        )

    def test_forget_existing(self):
        self.assertTrue(self.orchestrator.forget(self.record.memory_id))
        self.assertEqual(len(self.orchestrator.recall(MemoryQuery())), 0)

    def test_forget_missing_is_false(self):
        self.assertFalse(self.orchestrator.forget("nope"))

    def test_update_changes_only_supplied_fields(self):
        updated = self.orchestrator.update(
            self.record.memory_id, content="light mode"
        )
        self.assertEqual(updated.content, "light mode")
        self.assertEqual(updated.tags, ["ui"])  # preserved
        self.assertEqual(updated.importance, I.PERMANENT)  # preserved

    def test_update_tags_and_metadata(self):
        updated = self.orchestrator.update(
            self.record.memory_id, tags=["theme"], metadata={"v": 2}
        )
        self.assertEqual(updated.tags, ["theme"])
        self.assertEqual(updated.metadata, {"v": 2})

    def test_update_missing_raises(self):
        with self.assertRaises(MemoryNotFoundError):
            self.orchestrator.update("nope", content="x")


# =====================================================================
# Summarize
# =====================================================================
class SummarizeTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = _orchestrator()
        self.orchestrator.remember(C.USER_PREFERENCE, "a")
        self.orchestrator.remember(C.SYSTEM, "b")
        self.orchestrator.remember(C.APPROVAL, "c")

    def test_summarize_all(self):
        summary = self.orchestrator.summarize()
        self.assertIsInstance(summary, MemorySummary)
        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.by_category["USER_PREFERENCE"], 1)
        self.assertEqual(summary.by_importance["PERMANENT"], 2)
        self.assertEqual(len(summary.memory_ids), 3)

    def test_summarize_filtered(self):
        summary = self.orchestrator.summarize(MemoryQuery(category=C.APPROVAL))
        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.by_importance, {"SHORT_TERM": 1})


# =====================================================================
# Persistence integration
# =====================================================================
class PersistenceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = _orchestrator()
        self.instance = _instance()

    def test_remember_with_instance_persists_through_persistence(self):
        record = self.orchestrator.remember(
            C.WORKFLOW, "trip planned", workflow_instance=self.instance
        )
        self.assertEqual(record.workflow_id, self.instance.instance_id)
        self.assertEqual(record.persisted_version, 1)
        self.assertTrue(
            self.orchestrator.persistence.exists(self.instance.instance_id)
        )

    def test_persisted_workflow_loads_via_persistence(self):
        self.orchestrator.remember(
            C.WORKFLOW, "trip", workflow_instance=self.instance
        )
        loaded = self.orchestrator.persisted_workflow(
            self.instance.instance_id
        )
        self.assertEqual(loaded, self.instance)
        self.assertEqual(
            loaded.lifecycle_state.status, WorkflowLifecycleStatus.PENDING
        )

    def test_non_workflow_memory_persists_nothing(self):
        record = self.orchestrator.remember(C.USER_PREFERENCE, "dark mode")
        self.assertIsNone(record.persisted_version)

    def test_orchestrator_uses_persistence_manager_not_a_repository(self):
        self.assertIsInstance(self.orchestrator.persistence, PersistenceManager)


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = _orchestrator()
        self.record = self.orchestrator.remember(C.USER_PREFERENCE, "a")
        self.decision = self.orchestrator.decide(C.USER_PREFERENCE, "a")
        self.summary = self.orchestrator.summarize()

    def test_record_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.record.content = "b"

    def test_decision_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.decision.should_remember = False

    def test_query_is_frozen(self):
        query = MemoryQuery(category=C.SYSTEM)
        with self.assertRaises(ValidationError):
            query.category = C.WORKFLOW

    def test_summary_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.summary.total = 99


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_memory_classifier,
            get_memory_policy,
            get_memory_retriever,
        )

        self.assertIsInstance(get_memory_policy(), RuleBasedMemoryPolicy)
        self.assertIsInstance(
            get_memory_classifier(), RuleBasedMemoryClassifier
        )
        self.assertIsInstance(get_memory_retriever(), MemoryRetriever)

    def test_orchestrator_provider_wires_collaborators(self):
        from app.core.dependencies import get_memory_orchestrator

        orchestrator = get_memory_orchestrator()
        self.assertIsInstance(orchestrator, MemoryOrchestrator)
        self.assertIsInstance(orchestrator.policy, MemoryPolicy)
        self.assertIsInstance(orchestrator.classifier, MemoryClassifier)
        self.assertIsInstance(orchestrator.retriever, MemoryRetriever)
        self.assertIsInstance(orchestrator.persistence, PersistenceManager)

    def test_orchestrator_provider_uses_injected(self):
        from app.core.dependencies import get_memory_orchestrator

        policy = RuleBasedMemoryPolicy(rememberable={C.NOTIFICATION})
        orchestrator = get_memory_orchestrator(policy=policy)
        self.assertIs(orchestrator.policy, policy)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            MemoryClassifierDep,
            MemoryOrchestratorDep,
            MemoryPolicyDep,
            MemoryRetrieverDep,
        )

        for dep in (
            MemoryPolicyDep,
            MemoryClassifierDep,
            MemoryRetrieverDep,
            MemoryOrchestratorDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: prior sprints frozen; no capability/vector/embedding import
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_MODULES = {
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
        "vector_store",
        "embeddings",
        "embedding_service",
    }

    def test_frozen_165_persistence_engine_unchanged(self):
        from app.core.dependencies import get_persistence_engine
        import app.services.ai_employee.persistence as persistence_engine

        self.assertIsInstance(
            get_persistence_engine(), persistence_engine.PersistenceManager
        )

    def test_frozen_164_notification_engine_unchanged(self):
        from app.core.dependencies import get_notification_engine
        import app.services.ai_employee.notification as notification_engine

        self.assertIsInstance(
            get_notification_engine(), notification_engine.NotificationManager
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_older_semantic_memory_services_unchanged(self):
        # The Sprint 2/8–10 semantic-memory services are distinct and untouched.
        from app.services.memory import (
            MemoryPersistenceService,
            MemoryRetrievalService,
        )

        self.assertIsNot(MemoryPersistenceService, MemoryOrchestrator)
        self.assertIsNot(MemoryRetrievalService, MemoryRetriever)

    def test_memory_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.memory as pkg

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
