"""Scheduling Platform package (Sprint 16.7 — decide *when* workflows execute).

Adds the AI Employee Scheduling Platform: it decides *when* workflows execute and
delegates the running of due schedules down the chain ``ExecutionScheduler ->
WorkflowLifecycleManager -> WorkflowCoordinator``. It executes no workflow or
capability itself and uses only a deterministic caller-supplied integer *tick* —
no wall-clock, timer, ``time.sleep``, ``threading``, ``asyncio``, or cron. It
follows the flow ``SchedulerManager -> {SchedulePolicy, SchedulePlanner,
ScheduleQueue, ExecutionScheduler}`` (with the Sprint 16.5 Persistence and Sprint
16.4 Notification engines as integrations):

* the immutable DTOs :class:`ScheduleRequest`, :class:`ScheduleEntry`,
  :class:`ScheduleMetadata`, and :class:`ScheduleResult`, plus the
  :class:`ScheduleType` and :class:`ScheduleStatus` enums and the
  :class:`ScheduleError` hierarchy;
* the :class:`SchedulePolicy` abstraction with :class:`RequestSchedulePolicy`,
  :class:`ImmediatePolicy`, :class:`DelayedPolicy`, and :class:`RecurringPolicy`;
* the deterministic :class:`SchedulePlanner` (IMMEDIATE/DELAYED/AT_TIME/RECURRING);
* the deterministic tick-ordered :class:`ScheduleQueue`;
* the :class:`ExecutionScheduler` (delegates execution to the lifecycle manager,
  never the coordinator); and
* the :class:`SchedulerManager` coordinator.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.6, and it imports no capability module, no Workflow Coordinator, and no
timer/threading/asyncio/cron facility.
"""

from app.services.ai_employee.scheduler.execution import ExecutionScheduler
from app.services.ai_employee.scheduler.manager import SchedulerManager
from app.services.ai_employee.scheduler.models import (
    InvalidScheduleError,
    ScheduleEntry,
    ScheduleError,
    ScheduleMetadata,
    ScheduleNotFoundError,
    ScheduleRequest,
    ScheduleResult,
    ScheduleStatus,
    ScheduleType,
)
from app.services.ai_employee.scheduler.planner import SchedulePlanner
from app.services.ai_employee.scheduler.policy import (
    DelayedPolicy,
    ImmediatePolicy,
    RecurringPolicy,
    RequestSchedulePolicy,
    SchedulePolicy,
)
from app.services.ai_employee.scheduler.queue import ScheduleQueue

__all__ = [
    # DTOs & enums
    "ScheduleRequest",
    "ScheduleEntry",
    "ScheduleMetadata",
    "ScheduleResult",
    "ScheduleType",
    "ScheduleStatus",
    # errors
    "ScheduleError",
    "ScheduleNotFoundError",
    "InvalidScheduleError",
    # policy / planner / queue / execution / manager
    "SchedulePolicy",
    "RequestSchedulePolicy",
    "ImmediatePolicy",
    "DelayedPolicy",
    "RecurringPolicy",
    "SchedulePlanner",
    "ScheduleQueue",
    "ExecutionScheduler",
    "SchedulerManager",
]
