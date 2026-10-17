"""Opt-in PostgreSQL verification for project versioning and sequence locking."""

import os
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from types import SimpleNamespace

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Project, ProjectCheckpoint, User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import (
    ProjectCheckpointCreate,
    ProjectContextReplacement,
    ProjectCreate,
)
from app.services.project_service import (
    ProjectCheckpointConflictError,
    ProjectCheckpointService,
    ProjectService,
    ProjectVersionConflictError,
)


@unittest.skipUnless(
    os.environ.get("NEURAEVO_POSTGRES_INTEGRATION") == "1",
    "Run only in the dedicated PostgreSQL integration CI step.",
)
class ProjectPostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        if not settings.DATABASE_URL:
            self.fail("DATABASE_URL must target the disposable PostgreSQL test database.")
        self.engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.owner_id = uuid.uuid4()
        with self.Session() as session:
            session.add(
                User(
                    id=self.owner_id,
                    email=f"project-ci-{self.owner_id.hex}@example.test",
                    hashed_password="not-a-password",
                )
            )
            session.commit()
            owner = SimpleNamespace(id=self.owner_id)
            service = ProjectService(session)
            project = service.create_project(owner, ProjectCreate(name="CI Project"))
            self.project_id = project.id
            service.replace_approved_context(
                owner,
                project.id,
                ProjectContextReplacement(
                    objective="Verify PostgreSQL project locking.",
                    expected_version=project.version,
                    approved=True,
                ),
            )

    def tearDown(self):
        with self.Session() as session:
            user = session.get(User, self.owner_id)
            if user is not None:
                session.delete(user)
                session.commit()
        self.engine.dispose()

    def _save(self, label: str, backend_pid: Queue[int] | None = None) -> str:
        with self.Session() as session:
            owner = SimpleNamespace(id=self.owner_id)
            # Bound any unexpected lock wait so a failed assertion cannot hang CI.
            session.execute(text("SET LOCAL lock_timeout = '10s'"))
            session.execute(text("SET LOCAL statement_timeout = '15s'"))
            if backend_pid is not None:
                current_pid = session.scalar(text("SELECT pg_backend_pid()"))
                if current_pid is None:  # pragma: no cover - PostgreSQL invariant
                    raise AssertionError("PostgreSQL did not return a backend PID.")
                backend_pid.put(current_pid)
            try:
                checkpoint = ProjectCheckpointService(session).create_checkpoint(
                    owner,
                    self.project_id,
                    ProjectCheckpointCreate(
                        decisions=label,
                        request_id=uuid.uuid4(),
                        expected_version=2,
                        confirmed=True,
                    ),
                )
                return f"saved:{checkpoint.sequence}"
            except ProjectVersionConflictError:
                observed_version = session.scalar(
                    select(Project.version).where(Project.id == self.project_id)
                )
                session.rollback()
                return f"stale:{observed_version}"

    def _assert_database_reports_blocked(
        self,
        *,
        blocked_pid: int,
        blocker_pid: int,
        timeout: float = 5,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_observation = None
        with self.engine.connect() as observer:
            while time.monotonic() < deadline:
                row = observer.execute(
                    text(
                        """
                        SELECT state, wait_event_type, wait_event,
                               pg_blocking_pids(pid) AS blocking_pids
                        FROM pg_stat_activity
                        WHERE pid = :blocked_pid
                        """
                    ),
                    {"blocked_pid": blocked_pid},
                ).mappings().one_or_none()
                observer.rollback()
                if row is not None:
                    last_observation = {
                        "state": row["state"],
                        "wait_event_type": row["wait_event_type"],
                        "wait_event": row["wait_event"],
                        "blocking_pids": row["blocking_pids"],
                    }
                    if (
                        row["state"] == "active"
                        and row["wait_event_type"] == "Lock"
                        and blocker_pid in row["blocking_pids"]
                    ):
                        return
                time.sleep(0.05)
        self.fail(
            "PostgreSQL never reported the competing session waiting on "
            f"the lock holder; last observation: {last_observation!r}"
        )

    def test_competing_save_blocks_then_observes_stale_version(self):
        owner = SimpleNamespace(id=self.owner_id)
        backend_pid: Queue[int] = Queue(maxsize=1)
        with self.Session() as session_a:
            blocker_pid = session_a.scalar(text("SELECT pg_backend_pid()"))
            locked = ProjectRepository(session_a).get_owned_for_update(
                self.owner_id, self.project_id
            )
            self.assertIsNotNone(locked)
            self.assertEqual(locked.version, 2)

            pool = ThreadPoolExecutor(max_workers=1)
            competing = pool.submit(self._save, "Competing", backend_pid)
            try:
                try:
                    blocked_pid = backend_pid.get(timeout=5)
                except Empty:
                    self.fail("Competing session did not establish a database session.")
                self._assert_database_reports_blocked(
                    blocked_pid=blocked_pid,
                    blocker_pid=blocker_pid,
                )
                self.assertFalse(
                    competing.done(),
                    "Competing save completed despite PostgreSQL reporting its lock wait.",
                )
                winner = ProjectCheckpointService(session_a).create_checkpoint(
                    owner,
                    self.project_id,
                    ProjectCheckpointCreate(
                        decisions="Winner",
                        request_id=uuid.uuid4(),
                        expected_version=2,
                        confirmed=True,
                    ),
                )
                self.assertEqual(winner.sequence, 1)
                self.assertEqual(competing.result(timeout=5), "stale:3")
            finally:
                # On an assertion failure, release A's lock before waiting for B.
                if session_a.in_transaction():
                    session_a.rollback()
                pool.shutdown(wait=True, cancel_futures=True)

        with self.Session() as session:
            project = session.get(Project, self.project_id)
            checkpoints = session.scalars(
                select(ProjectCheckpoint)
                .where(
                    ProjectCheckpoint.project_id == self.project_id
                )
                .order_by(ProjectCheckpoint.sequence)
            ).all()
            self.assertEqual(project.version, 3)
            self.assertEqual(len(checkpoints), 1)
            self.assertEqual([row.sequence for row in checkpoints], [1])

    def test_rejected_save_releases_project_row_lock(self):
        owner = SimpleNamespace(id=self.owner_id)
        request_id = uuid.uuid4()
        with self.Session() as session_a:
            first = ProjectCheckpointService(session_a).create_checkpoint(
                owner,
                self.project_id,
                ProjectCheckpointCreate(
                    decisions="Original",
                    request_id=request_id,
                    expected_version=2,
                    confirmed=True,
                ),
            )
            self.assertEqual(first.sequence, 1)
            with self.assertRaises(ProjectCheckpointConflictError):
                ProjectCheckpointService(session_a).create_checkpoint(
                    owner,
                    self.project_id,
                    ProjectCheckpointCreate(
                        decisions="Changed",
                        request_id=request_id,
                        expected_version=3,
                        confirmed=True,
                    ),
                )
            self.assertFalse(session_a.in_transaction())

            with self.Session() as session_b:
                acquired = session_b.scalar(
                    select(Project)
                    .where(Project.id == self.project_id)
                    .with_for_update(nowait=True)
                )
                self.assertIsNotNone(acquired)
                session_b.rollback()


if __name__ == "__main__":
    unittest.main()

