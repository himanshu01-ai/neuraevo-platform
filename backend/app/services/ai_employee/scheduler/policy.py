"""Schedule policies (Sprint 16.7 — configurable scheduling rules).

Defines the :class:`SchedulePolicy` abstraction and its implementations. A policy
*adjusts a request* to enforce a scheduling rule, and the planner then computes the
tick from the adjusted request:

* :class:`RequestSchedulePolicy` — pass-through; respects the request's own type
  (the flexible default).
* :class:`ImmediatePolicy` — forces ``IMMEDIATE``.
* :class:`DelayedPolicy` — forces ``DELAYED`` with a configurable default delay.
* :class:`RecurringPolicy` — forces ``RECURRING`` with a configurable default
  interval.

Each policy is deterministic and stateless and returns a new immutable
:class:`ScheduleRequest` — it queues, plans, and executes nothing. Strictly
additive to Sprints 1.x–16.6.
"""

from abc import ABC, abstractmethod

from app.services.ai_employee.scheduler.models import (
    ScheduleRequest,
    ScheduleType,
)


class SchedulePolicy(ABC):
    """Abstraction that adjusts a request to enforce a scheduling rule (no execution).

    An implementation returns a possibly-adjusted :class:`ScheduleRequest` (the
    effective schedule). Implementations must be deterministic and must not queue,
    plan, or execute anything; the manager plans and queues the adjusted request.
    """

    @abstractmethod
    def apply(self, request: ScheduleRequest) -> ScheduleRequest:
        """Return the effective request after applying this policy's rule."""


class RequestSchedulePolicy(SchedulePolicy):
    """Pass-through policy — respects the request's own schedule type (default).

    Deterministic and stateless: ``apply`` returns the request unchanged, so the
    caller's own ``schedule_type`` and parameters drive the schedule. This is the
    flexible default when no specific policy is desired.
    """

    def apply(self, request: ScheduleRequest) -> ScheduleRequest:
        """Return ``request`` unchanged."""
        return request


class ImmediatePolicy(SchedulePolicy):
    """Policy that forces every request to schedule ``IMMEDIATE`` (run at now)."""

    def apply(self, request: ScheduleRequest) -> ScheduleRequest:
        """Return ``request`` forced to ``IMMEDIATE``."""
        return request.model_copy(
            update={"schedule_type": ScheduleType.IMMEDIATE}
        )


class DelayedPolicy(SchedulePolicy):
    """Policy that forces ``DELAYED`` with a configurable default delay.

    Constructed with a ``default_delay`` (ticks). ``apply`` forces ``DELAYED`` and
    fills the delay with the request's own value when set, else the default.
    Deterministic and stateless.
    """

    def __init__(self, default_delay: int = 1) -> None:
        self.default_delay = max(default_delay, 0)

    def apply(self, request: ScheduleRequest) -> ScheduleRequest:
        """Return ``request`` forced to ``DELAYED`` with the effective delay."""
        delay = request.delay if request.delay else self.default_delay
        return request.model_copy(
            update={"schedule_type": ScheduleType.DELAYED, "delay": delay}
        )


class RecurringPolicy(SchedulePolicy):
    """Policy that forces ``RECURRING`` with a configurable default interval.

    Constructed with a ``default_interval`` (ticks). ``apply`` forces ``RECURRING``
    and fills the interval with the request's own value when set, else the default.
    Deterministic and stateless.
    """

    def __init__(self, default_interval: int = 1) -> None:
        self.default_interval = max(default_interval, 1)

    def apply(self, request: ScheduleRequest) -> ScheduleRequest:
        """Return ``request`` forced to ``RECURRING`` with the effective interval."""
        interval = (
            request.interval
            if request.interval is not None
            else self.default_interval
        )
        return request.model_copy(
            update={
                "schedule_type": ScheduleType.RECURRING,
                "interval": interval,
            }
        )
