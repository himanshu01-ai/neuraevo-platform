"""Schedule planner (Sprint 16.7 — deterministic next-execution tick math).

Defines :class:`SchedulePlanner`, the deterministic component that computes *when*
a workflow should execute, expressed as an integer *tick*. It supports the four
schedule types — ``IMMEDIATE`` (now), ``DELAYED`` (now + delay), ``AT_TIME`` (a
target tick), and ``RECURRING`` (now + initial offset, then every interval) — and
computes the next recurrence tick.

There is no wall-clock, timer, or sleep dependency: the "now" tick is supplied by
the caller and all arithmetic is pure and deterministic — the same inputs always
yield the same tick. It holds no state and executes nothing. Strictly additive to
Sprints 1.x–16.6.
"""

from app.services.ai_employee.scheduler.models import (
    InvalidScheduleError,
    ScheduleRequest,
    ScheduleType,
)


class SchedulePlanner:
    """Computes deterministic next-execution ticks (no wall-clock, no execution).

    Stateless: ``plan`` computes the initial execution tick for a request relative
    to a caller-supplied ``now_tick``, and ``next_recurrence`` computes the tick of
    the following occurrence of a recurring schedule. It validates that ``AT_TIME``
    carries a target tick and ``RECURRING`` an interval, raising
    :class:`InvalidScheduleError` otherwise. Same inputs in -> same tick out.
    """

    def plan(self, request: ScheduleRequest, now_tick: int) -> int:
        """Return the initial execution tick for ``request`` relative to ``now_tick``.

        ``IMMEDIATE`` -> ``now_tick``; ``DELAYED`` -> ``now_tick + delay``;
        ``AT_TIME`` -> the request's ``at_tick`` (required); ``RECURRING`` ->
        ``now_tick + delay`` as the first occurrence (interval required). Raises
        :class:`InvalidScheduleError` for a missing ``at_tick``/``interval``.
        """
        schedule_type = request.schedule_type
        if schedule_type == ScheduleType.IMMEDIATE:
            return now_tick
        if schedule_type == ScheduleType.DELAYED:
            return now_tick + request.delay
        if schedule_type == ScheduleType.AT_TIME:
            if request.at_tick is None:
                raise InvalidScheduleError(
                    "AT_TIME schedule requires an at_tick"
                )
            return request.at_tick
        if schedule_type == ScheduleType.RECURRING:
            if request.interval is None:
                raise InvalidScheduleError(
                    "RECURRING schedule requires an interval"
                )
            return now_tick + request.delay
        raise InvalidScheduleError(
            f"unknown schedule type: {schedule_type!r}"
        )

    def next_recurrence(self, current_tick: int, interval: int) -> int:
        """Return the tick of the next occurrence after ``current_tick``."""
        return current_tick + interval
