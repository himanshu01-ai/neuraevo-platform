"""Unit + integration tests for the Sprint 16.5 Persistence Layer.

Exercises the production-grade persistence subsystem: the
:class:`PersistenceRepository` abstraction with
:class:`InMemoryPersistenceRepository` (owns storage), the
:class:`PersistenceManager` engine (owns persistence decisions — versioning,
snapshotting, validation), the immutable snapshot/version/history DTOs, and the
deterministic validation errors. It stores *platform state* only — no database, AI
memory, or vector store. Snapshots are built from the frozen Sprint 16.2
:class:`WorkflowInstance`.

Covers, as the sprint requires: save, load, delete, exists, snapshot, restore,
version history, latest version, invalid restore, duplicate saves, the repository
abstraction, DTO immutability, DI wiring, and regression (Sprints 16.1–16.4
unchanged; the frozen persistence abstraction still works; the persistence
sub-package imports no capability module).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_persistence_layer
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
from app.services.ai_employee.persistence import (
    DuplicatePersistenceError,
    InMemoryPersistenceRepository,
    InvalidRestoreError,
    InvalidSnapshotError,
    MissingVersionError,
    MissingWorkflowError,
    PersistenceHistory,
    PersistenceManager,
    PersistenceMetadata,
    PersistenceRepository,
    PersistenceResult,
    PersistenceSnapshot,
    PersistenceVersion,
    SnapshotType,
)
from app.services.runtime.workflow_models import WorkflowStep


# =====================================================================
# Helpers
# =====================================================================
def _lifecycle_manager():
    from app.core.dependencies import get_workflow_lifecycle_manager

    return get_workflow_lifecycle_manager()


def _instance(task_id="t1", lifecycle=None):
    lifecycle = lifecycle or _lifecycle_manager()
    return lifecycle.create_instance(
        EmployeeProfile(employee_id="e1", name="Ada"),
        TaskDelegation(task_id=task_id, task="do it"),
        [WorkflowStep(step_id="s1", capability_name="demo")],
    )


def _engine():
    return PersistenceManager(InMemoryPersistenceRepository())


# =====================================================================
# Save / exists / load
# =====================================================================
class SaveLoadTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.instance = _instance()
        self.key = self.instance.instance_id

    def test_first_save_is_version_one(self):
        result = self.engine.save(self.instance)
        self.assertIsInstance(result, PersistenceResult)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "save")
        self.assertEqual(result.version, 1)

    def test_each_save_creates_a_new_version(self):
        self.assertEqual(self.engine.save(self.instance).version, 1)
        self.assertEqual(self.engine.save(self.instance).version, 2)
        self.assertEqual(self.engine.save(self.instance).version, 3)

    def test_exists_reflects_persistence(self):
        self.assertFalse(self.engine.exists(self.key))
        self.engine.save(self.instance)
        self.assertTrue(self.engine.exists(self.key))

    def test_load_returns_latest_instance(self):
        self.engine.save(self.instance)
        started = _lifecycle_manager().start(self.instance)
        self.engine.save(started)
        loaded = self.engine.load(self.key)
        self.assertEqual(
            loaded.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )

    def test_load_missing_raises(self):
        with self.assertRaises(MissingWorkflowError):
            self.engine.load("nope")

    def test_save_is_deterministic(self):
        first = _engine().save(self.instance)
        second = _engine().save(self.instance)
        self.assertEqual(first.snapshot, second.snapshot)
        self.assertEqual(first.version, second.version)


# =====================================================================
# Snapshot construction & content areas
# =====================================================================
class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.instance = _instance()

    def test_snapshot_captures_instance_progress_and_metadata(self):
        snapshot = self.engine.snapshot(self.instance)
        self.assertIsInstance(snapshot, PersistenceSnapshot)
        self.assertEqual(snapshot.instance, self.instance)
        self.assertEqual(snapshot.progress, self.instance.progress)
        self.assertEqual(
            snapshot.workflow_metadata, self.instance.instance_metadata
        )
        self.assertIsInstance(snapshot.metadata, PersistenceMetadata)

    def test_snapshot_captures_approval_and_notification_history(self):
        approvals = [{"decision": "APPROVED"}]
        notifications = [{"event": "WORKFLOW_STARTED"}]
        snapshot = self.engine.snapshot(
            self.instance,
            approval_history=approvals,
            notification_history=notifications,
        )
        self.assertEqual(snapshot.approval_history, approvals)
        self.assertEqual(snapshot.notification_history, notifications)

    def test_snapshot_types_supported(self):
        for snapshot_type in SnapshotType:
            snapshot = self.engine.snapshot(
                self.instance, snapshot_type=snapshot_type
            )
            self.assertEqual(snapshot.snapshot_type, snapshot_type)
            self.assertEqual(snapshot.metadata.snapshot_type, snapshot_type)

    def test_standalone_snapshot_is_unversioned(self):
        self.assertEqual(self.engine.snapshot(self.instance).metadata.version, 0)

    def test_snapshot_missing_instance_raises(self):
        with self.assertRaises(InvalidSnapshotError):
            self.engine.snapshot(None)

    def test_save_persists_the_snapshot_type(self):
        result = self.engine.save(
            self.instance, snapshot_type=SnapshotType.AUTO
        )
        self.assertEqual(result.snapshot.snapshot_type, SnapshotType.AUTO)


# =====================================================================
# Versioning: latest / history / restore
# =====================================================================
class VersioningTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.lifecycle = _lifecycle_manager()
        self.instance = _instance(lifecycle=self.lifecycle)
        self.key = self.instance.instance_id
        self.engine.save(self.instance)  # v1 (PENDING)
        self.started = self.lifecycle.start(self.instance)
        self.engine.save(self.started)  # v2 (RUNNING)

    def test_version_returns_latest_number(self):
        self.assertEqual(self.engine.version(self.key), 2)

    def test_latest_returns_latest_version_record(self):
        latest = self.engine.latest(self.key)
        self.assertIsInstance(latest, PersistenceVersion)
        self.assertEqual(latest.version, 2)
        self.assertEqual(
            latest.snapshot.instance.lifecycle_state.status,
            WorkflowLifecycleStatus.RUNNING,
        )

    def test_history_lists_versions_in_order(self):
        history = self.engine.history(self.key)
        self.assertIsInstance(history, PersistenceHistory)
        self.assertEqual(history.total, 2)
        self.assertEqual(history.latest_version, 2)
        self.assertEqual([v.version for v in history.versions], [1, 2])

    def test_restore_returns_the_versioned_snapshot(self):
        v1 = self.engine.restore(self.key, 1)
        self.assertIsInstance(v1, PersistenceSnapshot)
        self.assertEqual(
            v1.instance.lifecycle_state.status,
            WorkflowLifecycleStatus.PENDING,
        )
        v2 = self.engine.restore(self.key, 2)
        self.assertEqual(
            v2.instance.lifecycle_state.status,
            WorkflowLifecycleStatus.RUNNING,
        )

    def test_version_missing_workflow_raises(self):
        with self.assertRaises(MissingWorkflowError):
            self.engine.version("nope")

    def test_history_missing_workflow_raises(self):
        with self.assertRaises(MissingWorkflowError):
            self.engine.history("nope")


# =====================================================================
# Delete
# =====================================================================
class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.instance = _instance()
        self.key = self.instance.instance_id
        self.engine.save(self.instance)

    def test_delete_removes_all_versions(self):
        self.engine.save(self.instance)  # v2
        result = self.engine.delete(self.key)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "delete")
        self.assertFalse(self.engine.exists(self.key))

    def test_delete_missing_raises(self):
        with self.assertRaises(MissingWorkflowError):
            self.engine.delete("nope")


# =====================================================================
# Validation
# =====================================================================
class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.instance = _instance()
        self.key = self.instance.instance_id
        self.engine.save(self.instance)

    def test_invalid_restore_non_positive_version(self):
        with self.assertRaises(InvalidRestoreError):
            self.engine.restore(self.key, 0)
        with self.assertRaises(InvalidRestoreError):
            self.engine.restore(self.key, -1)

    def test_restore_missing_workflow_raises(self):
        with self.assertRaises(MissingWorkflowError):
            self.engine.restore("nope", 1)

    def test_restore_missing_version_raises(self):
        with self.assertRaises(MissingVersionError):
            self.engine.restore(self.key, 99)

    def test_save_missing_instance_raises(self):
        with self.assertRaises(InvalidSnapshotError):
            self.engine.save(None)

    def test_duplicate_save_at_repository_raises(self):
        repository = self.engine.repository
        duplicate = repository.get(self.key, 1)
        with self.assertRaises(DuplicatePersistenceError):
            repository.save(duplicate)


# =====================================================================
# Repository abstraction
# =====================================================================
class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryPersistenceRepository()
        self.engine = _engine()
        self.instance = _instance()
        self.key = self.instance.instance_id
        # Build two real version records via a manager, then store them here.
        self.v1 = PersistenceVersion(
            workflow_id=self.key,
            version=1,
            snapshot=self.engine.snapshot(self.instance, version=1),
        )
        self.v2 = PersistenceVersion(
            workflow_id=self.key,
            version=2,
            snapshot=self.engine.snapshot(self.instance, version=2),
        )

    def test_is_a_persistence_repository(self):
        self.assertIsInstance(self.repository, PersistenceRepository)

    def test_save_get_and_exists(self):
        self.assertFalse(self.repository.exists(self.key))
        self.repository.save(self.v1)
        self.assertTrue(self.repository.exists(self.key))
        self.assertEqual(self.repository.get(self.key, 1), self.v1)
        self.assertIsNone(self.repository.get(self.key, 5))

    def test_versions_are_ascending(self):
        self.repository.save(self.v2)
        self.repository.save(self.v1)
        self.assertEqual(
            [v.version for v in self.repository.versions(self.key)], [1, 2]
        )

    def test_latest_is_highest_version(self):
        self.repository.save(self.v1)
        self.repository.save(self.v2)
        self.assertEqual(self.repository.latest(self.key), self.v2)

    def test_delete_reports_existence(self):
        self.repository.save(self.v1)
        self.assertTrue(self.repository.delete(self.key))
        self.assertFalse(self.repository.delete(self.key))

    def test_duplicate_version_rejected(self):
        self.repository.save(self.v1)
        with self.assertRaises(DuplicatePersistenceError):
            self.repository.save(self.v1)

    def test_manager_delegates_storage_to_repository(self):
        # The manager owns decisions but no storage: it exposes only the repository
        # + its sequence counter, and every save lands in the repository.
        self.assertEqual(set(vars(self.engine)), {"repository", "_sequence"})
        self.engine.save(self.instance)
        self.assertTrue(self.engine.repository.exists(self.key))


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.instance = _instance()
        self.result = self.engine.save(self.instance)
        self.snapshot = self.result.snapshot
        self.history = self.engine.history(self.instance.instance_id)

    def test_snapshot_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.snapshot.workflow_id = "other"

    def test_metadata_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.snapshot.metadata.version = 99

    def test_version_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.history.versions[0].version = 99

    def test_history_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.history.total = 99

    def test_result_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.success = False


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_repository_provider(self):
        from app.core.dependencies import get_persistence_repository

        self.assertIsInstance(
            get_persistence_repository(), InMemoryPersistenceRepository
        )

    def test_engine_provider_wires_repository(self):
        from app.core.dependencies import get_persistence_engine

        engine = get_persistence_engine()
        self.assertIsInstance(engine, PersistenceManager)
        self.assertIsInstance(engine.repository, PersistenceRepository)

    def test_engine_provider_uses_injected_repository(self):
        from app.core.dependencies import get_persistence_engine

        repository = InMemoryPersistenceRepository()
        engine = get_persistence_engine(repository)
        self.assertIs(engine.repository, repository)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            PersistenceEngineDep,
            PersistenceRepositoryDep,
        )

        self.assertIsNotNone(PersistenceRepositoryDep)
        self.assertIsNotNone(PersistenceEngineDep)

    def test_wired_engine_round_trips(self):
        from app.core.dependencies import get_persistence_engine

        engine = get_persistence_engine()
        instance = _instance()
        engine.save(instance)
        self.assertEqual(
            engine.load(instance.instance_id), instance
        )


# =====================================================================
# Regression: prior sprints frozen; frozen persistence intact; no capability
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_CAPABILITY_MODULES = {
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
    }

    def test_frozen_162_persistence_manager_unchanged(self):
        # The frozen Sprint 16.2 PersistenceManager ABC + InMemoryPersistenceManager
        # still exist and behave as before (distinct from the Sprint 16.5 engine).
        from app.core.dependencies import get_persistence_manager
        from app.services.ai_employee import (
            InMemoryPersistenceManager as FrozenInMemory,
        )
        from app.services.ai_employee import (
            PersistenceManager as FrozenPersistenceManager,
        )

        frozen = get_persistence_manager()
        self.assertIsInstance(frozen, FrozenInMemory)
        self.assertIsInstance(frozen, FrozenPersistenceManager)
        self.assertIsNot(FrozenPersistenceManager, PersistenceManager)

    def test_frozen_164_notification_engine_unchanged(self):
        from app.core.dependencies import get_notification_engine
        import app.services.ai_employee.notification as notification_engine

        self.assertIsInstance(
            get_notification_engine(), notification_engine.NotificationManager
        )

    def test_frozen_163_approval_engine_unchanged(self):
        from app.core.dependencies import get_approval_engine
        import app.services.ai_employee.approval as approval_engine

        self.assertIsInstance(
            get_approval_engine(), approval_engine.ApprovalManager
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_persistence_package_imports_no_capability_module(self):
        import app.services.ai_employee.persistence as pkg

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
                    if tail in self._FORBIDDEN_CAPABILITY_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
