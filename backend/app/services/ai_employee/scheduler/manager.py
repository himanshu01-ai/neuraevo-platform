"""Scheduler manager (Sprint 16.7 — coordinate scheduling; decide *when*, never run).

Defines :class:`SchedulerManager`, the coordinator of the Scheduling Platform. It
decides *when* workflows execute and delegates the running of due schedules to the
:class:`ExecutionScheduler` (which delegates to the frozen
:class:`WorkflowLifecycleManager`). It never executes a workflow or capability
itself.

It coordinates the injected schedule policy, planner, and queue, and integrates
with the Sprint 16.5 :class:`PersistenceManager` (persisting each scheduled
workflow) and the Sprint 16.4 notification engine (announcing execution and
cancellation). All timing is a deterministic integer *tick* supplied by the caller
— there is no wall-clock, timer, ``time.sleep``, ``threading``, ``asyncio``, or
cron. Constructor injection only; its only mutable state is a deterministic
sequence counter — no static, singleton, or service-locator state. Strictly
additive to Sprints 1.x–16.6, whose modules are left untouched.
"""

from typing import List

from app.services.ai_employee.notification.manager import NotificationManager
from app.services.ai_employee.notification.models import NotificationEvent
from app.services.ai_employee.persistence.manager import PersistenceManager
from app.services.ai_employee.platform_models import WorkflowInstance
from app.services.ai_employee.scheduler.execution import ExecutionScheduler
from app.services.ai_employee.scheduler.models import (
    ScheduleEntry,
    ScheduleMetadata,
    ScheduleNotFoundError,
    ScheduleRequest,
    ScheduleResult,
    ScheduleStatus,
    ScheduleType,
)
from app.services.ai_employee.scheduler.planner import SchedulePlanner
from app.services.ai_employee.scheduler.policy import SchedulePolicy
from app.services.ai_employee.scheduler.queue import ScheduleQueue


class SchedulerManager:
    """Coordinates scheduling over policy, planner, queue, execution, and integrations.

    Constructed with an injected :class:`SchedulePolicy`, :class:`SchedulePlanner`,
    :class:`ScheduleQueue`, :class:`ExecutionScheduler`, Sprint 16.5
    :class:`PersistenceManager`, and Sprint 16.4 :class:`NotificationManager`
    (constructor injection; it instantiates none of them). It schedules, cancels,
    reschedules, lists, pauses/resumes, and runs due schedules — delegating every
    execution to the :class:`ExecutionScheduler` and never executing a workflow or
    capability itself. It holds a deterministic sequence counter only.
    """

    def __init__(
        self,
        policy: SchedulePolicy,
        planner: SchedulePlanner,
        queue: ScheduleQueue,
        execution_scheduler: ExecutionScheduler,
        persistence: PersistenceManager,
        notification_manager: NotificationManager,
    ) -> None:
        self.policy = policy
        self.planner = planner
        self.queue = queue
        self.execution_scheduler = execution_scheduler
        self.persistence = persistence
        self.notification_manager = notification_manager
        self._sequence = 0

    # --- scheduling ------------------------------------------------------
    def schedule(
        self,
        request: ScheduleRequest,
        instance: WorkflowInstance,
        now_tick: int = 0,
    ) -> ScheduleResult:
        """Schedule ``instance`` per ``request`` and return the result (no execution).

        Applies the policy, computes the deterministic execution tick via the
        planner, persists the workflow instance through the Persistence Layer, builds
        a ``SCHEDULED`` :class:`ScheduleEntry`, and enqueues it. Nothing is executed.
        """
        effective = self.policy.apply(request)
        next_tick = self.planner.plan(effective, now_tick)
        self.persistence.save(instance)

        sequence = self._next()
        entry_id = f"schedule-{instance.instance_id}-{sequence}"
        entry = ScheduleEntry(
            entry_id=entry_id,
            workflow_id=instance.instance_id,
            instance=instance,
            schedule_type=effective.schedule_type,
            status=ScheduleStatus.SCHEDULED,
            next_execution_tick=next_tick,
            interval=effective.interval,
            occurrences=0,
            max_occurrences=effective.max_occurrences,
            created_at_tick=now_tick,
            metadata=ScheduleMetadata(
                schedule_id=entry_id,
                schedule_type=effective.schedule_type,
                created_at_tick=now_tick,
                interval=effective.interval,
            ),
        )
        self.queue.enqueue(entry)
        return ScheduleResult(
            entry_id=entry_id,
            workflow_id=entry.workflow_id,
            operation="schedule",
            success=True,
            entry=entry,
        )

    def cancel(self, entry_id: str) -> ScheduleResult:
        """Cancel and remove the scheduled entry; record a cancellation notification.

        Raises :class:`ScheduleNotFoundError` when the entry is not queued.
        """
        entry = self.queue.remove(entry_id)
        if entry is None:
            raise ScheduleNotFoundError(f"no such schedule: {entry_id}")
        cancelled = entry.model_copy(
            update={"status": ScheduleStatus.CANCELLED}
        )
        self.notification_manager.notify(
            NotificationEvent.WORKFLOW_CANCELLED, entry.workflow_id
        )
        return ScheduleResult(
            entry_id=entry_id,
            workflow_id=entry.workflow_id,
            operation="cancel",
            success=True,
            entry=cancelled,
        )

    def reschedule(
        self,
        entry_id: str,
        request: ScheduleRequest,
        now_tick: int = 0,
    ) -> ScheduleResult:
        """Recompute a queued entry's execution tick from ``request`` and update it.

        Raises :class:`ScheduleNotFoundError` when the entry is not queued. Keeps the
        same ``entry_id`` and workflow instance; recomputes the type, tick, interval,
        and bound via the policy and planner, and resets the status to ``SCHEDULED``.
        """
        existing = self.queue.get(entry_id)
        if existing is None:
            raise ScheduleNotFoundError(f"no such schedule: {entry_id}")
        effective = self.policy.apply(request)
        next_tick = self.planner.plan(effective, now_tick)
        updated = existing.model_copy(
            update={
                "schedule_type": effective.schedule_type,
                "status": ScheduleStatus.SCHEDULED,
                "next_execution_tick": next_tick,
                "interval": effective.interval,
                "max_occurrences": effective.max_occurrences,
            }
        )
        self.queue.update(updated)
        return ScheduleResult(
            entry_id=entry_id,
            workflow_id=existing.workflow_id,
            operation="reschedule",
            success=True,
            entry=updated,
        )

    def list(self) -> List[ScheduleEntry]:
        """Return all queued schedule entries in tick order."""
        return self.queue.pending()

    # --- pause / resume --------------------------------------------------
    def pause(self, entry_id: str) -> ScheduleResult:
        """Pause a queued entry (held from execution) via the execution scheduler.

        Raises :class:`ScheduleNotFoundError` when the entry is not queued.
        """
        entry = self.queue.get(entry_id)
        if entry is None:
            raise ScheduleNotFoundError(f"no such schedule: {entry_id}")
        paused = self.execution_scheduler.pause_execution(entry)
        self.queue.update(paused)
        return ScheduleResult(
            entry_id=entry_id,
            workflow_id=entry.workflow_id,
            operation="pause",
            success=True,
            entry=paused,
        )

    def resume(self, entry_id: str) -> ScheduleResult:
        """Resume a paused entry (eligible again) via the execution scheduler.

        Raises :class:`ScheduleNotFoundError` when the entry is not queued.
        """
        entry = self.queue.get(entry_id)
        if entry is None:
            raise ScheduleNotFoundError(f"no such schedule: {entry_id}")
        resumed = self.execution_scheduler.resume_execution(entry)
        self.queue.update(resumed)
        return ScheduleResult(
            entry_id=entry_id,
            workflow_id=entry.workflow_id,
            operation="resume",
            success=True,
            entry=resumed,
        )

    # --- running due schedules ------------------------------------------
    def run_due(self, now_tick: int) -> List[ScheduleResult]:
        """Run every schedule due at or before ``now_tick`` and return the results.

        Dequeues the due ``SCHEDULED`` entries, and for each one records a
        ``WORKFLOW_STARTED`` notification, delegates execution to the
        :class:`ExecutionScheduler` (which delegates to the lifecycle manager), and —
        for a recurring schedule still within its bound — re-enqueues the next
        occurrence at the planner's next tick. The manager decides *when* and
        delegates the running; it executes no workflow or capability itself.
        """
        due = self.queue.dequeue_due(now_tick)
        results: List[ScheduleResult] = []
        for entry in due:
            self.notification_manager.notify(
                NotificationEvent.WORKFLOW_STARTED, entry.workflow_id
            )
            results.append(self.execution_scheduler.execute_entry(entry))
            if (
                entry.schedule_type == ScheduleType.RECURRING
                and self._can_recur(entry)
            ):
                next_tick = self.planner.next_recurrence(
                    entry.next_execution_tick, entry.interval
                )
                self.queue.enqueue(
                    entry.model_copy(
                        update={
                            "status": ScheduleStatus.SCHEDULED,
                            "next_execution_tick": next_tick,
                            "occurrences": entry.occurrences + 1,
                        }
                    )
                )
        return results

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _can_recur(entry: ScheduleEntry) -> bool:
        """Return whether a recurring ``entry`` still has occurrences remaining."""
        return (
            entry.max_occurrences is None
            or entry.occurrences + 1 < entry.max_occurrences
        )

    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
