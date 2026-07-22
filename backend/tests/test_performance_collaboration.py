"""Performance regression guards for the collaboration read surfaces.

These are *scaling* tests, not micro-benchmarks: they count the SQL statements a
read issues and assert the count does not grow with the number of rows returned.
That is the property an N+1 breaks — resolving each row's actor name with its own
query makes a page of N rows cost N follow-up reads — so pinning the count makes a
regression fail loudly here rather than show up as latency in production.

Three hot read paths are covered, each of which previously resolved a display
name per row and now batch-loads every distinct actor once:

* the activity timeline (:meth:`ActivityService.list_for_resource`),
* the notification inbox (:meth:`NotificationService.list_for_user`),
* the participant list (:meth:`CollaborationService.list_participants`).

The engine is instrumented with a ``before_cursor_execute`` listener so the count
is the real number of round-trips, and ``expire_all`` is called before each
measurement so name lookups actually hit the database instead of the session's
identity map.

    PYTHONPATH=. python -m unittest tests.test_performance_collaboration
"""

import unittest
import uuid

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.activity_event import ActivityEvent
from app.models.collaboration_participant import CollaborationParticipant
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.services.collaboration.activity_service import ActivityService
from app.services.collaboration.notification_service import NotificationService
from app.services.collaboration.service import CollaborationService
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
    CollaborationRole,
    NotificationType,
    ParticipantType,
)


class _SelectCounter:
    """Counts SELECT statements executed on an engine while active."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.count = 0

    def _before(self, conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            self.count += 1

    def __enter__(self) -> "_SelectCounter":
        event.listen(self.engine, "before_cursor_execute", self._before)
        return self

    def __exit__(self, *exc) -> None:
        event.remove(self.engine, "before_cursor_execute", self._before)


class CollaborationReadScalingTests(unittest.TestCase):
    """Every collaboration read stays O(1) in the number of rows it returns."""

    #: Two page sizes far enough apart that an N+1 would show a clear difference.
    SMALL = 3
    LARGE = 24

    def _make_engine(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        return engine

    def _seed(self, n: int):
        """An owner, a task they own, and ``n`` distinct actors that each left an
        activity event, a notification, and a participant row."""
        engine = self._make_engine()
        session: Session = sessionmaker(bind=engine, expire_on_commit=False)()

        owner = User(
            id=uuid.uuid4(),
            email="owner@perf.dev",
            hashed_password="x",
            full_name="Olivia Owner",
            is_active=True,
        )
        session.add(owner)
        task = Task(
            id=uuid.uuid4(),
            user_id=owner.id,
            business_id="TSK-PERF",
            name="Performance resource",
        )
        session.add(task)

        actors = [
            User(
                id=uuid.uuid4(),
                email=f"actor{i}@perf.dev",
                hashed_password="x",
                full_name=f"Actor {i}",
                is_active=True,
            )
            for i in range(n)
        ]
        session.add_all(actors)
        session.commit()

        rtype = CollaborationResourceType.TASK.value
        for i, actor in enumerate(actors, start=1):
            session.add(
                ActivityEvent(
                    id=uuid.uuid4(),
                    resource_type=rtype,
                    resource_id=task.id,
                    owner_user_id=owner.id,
                    actor_type=ActivityActorType.USER.value,
                    actor_id=actor.id,
                    kind=ActivityKind.PARTICIPANT_ADDED.value,
                    summary=f"Actor {i} acted",
                    sequence=i,
                )
            )
            session.add(
                Notification(
                    id=uuid.uuid4(),
                    user_id=owner.id,
                    type=NotificationType.TASK.value,
                    title=f"Notice {i}",
                    description="",
                    resource_type=rtype,
                    resource_id=task.id,
                    actor_type=ActivityActorType.USER.value,
                    actor_id=actor.id,
                )
            )
            session.add(
                CollaborationParticipant(
                    id=uuid.uuid4(),
                    resource_type=rtype,
                    resource_id=task.id,
                    participant_type=ParticipantType.USER.value,
                    user_id=actor.id,
                    role=CollaborationRole.VIEWER.value,
                    added_by_user_id=owner.id,
                )
            )
        session.commit()
        return engine, session, owner, task

    def _measure(self, build_service, call):
        """Query count for ``call`` at both page sizes, with a cold identity map."""
        counts = {}
        for label, n in (("small", self.SMALL), ("large", self.LARGE)):
            engine, session, owner, task = self._seed(n)
            service = build_service(session)
            session.expire_all()  # force real reads, not identity-map hits
            with _SelectCounter(engine) as counter:
                result = call(service, owner, task)
            self.assertEqual(len(result), self._expected_len(label, n))
            counts[label] = counter.count
            session.close()
            engine.dispose()
        return counts

    def _expected_len(self, label: str, n: int) -> int:
        # Participant list prepends the synthetic owner entry; the others don't.
        return n

    def _assert_constant(self, counts: dict, ceiling: int) -> None:
        self.assertEqual(
            counts["small"],
            counts["large"],
            f"query count scaled with rows ({counts}) — N+1 regression",
        )
        self.assertLessEqual(counts["large"], ceiling)

    # --- The three read surfaces ----------------------------------------

    def test_activity_timeline_is_constant_query_count(self):
        counts = self._measure(
            ActivityService,
            lambda s, owner, task: s.list_for_resource(
                owner, CollaborationResourceType.TASK, task.id
            ),
        )
        # get_access (resolve + role) + events read + one batched user read.
        self._assert_constant(counts, ceiling=8)

    def test_notification_inbox_is_constant_query_count(self):
        counts = self._measure(
            NotificationService,
            lambda s, owner, task: s.list_for_user(owner),
        )
        # inbox read + one batched user read.
        self._assert_constant(counts, ceiling=6)

    def test_participant_list_is_constant_query_count(self):
        def call(service, owner, task):
            people = service.list_participants(
                owner, CollaborationResourceType.TASK, task.id
            )
            # Drop the synthetic owner entry so the length check matches n.
            return [p for p in people if not p.is_owner]

        counts = self._measure(CollaborationService, call)
        # require (resolve + role) + participants read + one batched user read.
        self._assert_constant(counts, ceiling=8)

    # --- Correctness alongside the batching -----------------------------

    def test_batched_names_match_per_row_resolution(self):
        """Batch resolution returns exactly the names a per-row resolve would."""
        engine, session, owner, task = self._seed(5)
        activity = ActivityService(session)
        events = activity.list_for_resource(
            owner, CollaborationResourceType.TASK, task.id
        )
        # Newest first: sequence 5..1 -> "Actor 4".."Actor 0".
        self.assertEqual(
            [e.actor_name for e in events],
            [f"Actor {i}" for i in range(4, -1, -1)],
        )
        session.close()
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
