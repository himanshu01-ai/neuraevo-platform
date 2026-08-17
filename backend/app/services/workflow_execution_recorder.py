"""Observing a run from outside it (Sprint 18.10).

The runtime keeps no clock. A :class:`WorkflowExecutionResult` says what each
step produced and whether it succeeded, but not when it started or how long it
took — and Sprint 18.10 must not give the engine a clock, because that would be
redesigning it.

So the timings are taken from outside, through a seam that already exists. The
coordinator is *given* its :class:`CapabilityRouter`; it calls ``dispatch`` once
per step and never inspects what it was handed. Passing it a router that records
when each dispatch began and ended yields per-step timings with the coordinator
unchanged, unaware, and running exactly the steps it was going to run.

This module holds nothing else. It does not decide what to store, does not touch
a session, and does not alter a result — it watches, and the execution service
reads what it saw.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
)


@dataclass(frozen=True)
class StepTiming:
    """When one step ran, and for how long."""

    started_at: datetime
    finished_at: datetime
    duration_ms: int


@dataclass
class ExecutionLogRecord:
    """One structured thing worth saying about a run.

    A record rather than a line of prose, so a reader can filter by level or by
    step without parsing anything. ``message`` is written for a person: no
    traceback, no exception class, nothing describing the server.
    """

    level: str
    message: str
    step_id: Optional[str] = None


@dataclass
class ExecutionLog:
    """The messages a run accumulated, in the order they were made."""

    records: List[ExecutionLogRecord] = field(default_factory=list)

    def info(self, message: str, step_id: Optional[str] = None) -> None:
        self.records.append(ExecutionLogRecord("info", message, step_id))

    def warning(self, message: str, step_id: Optional[str] = None) -> None:
        self.records.append(ExecutionLogRecord("warning", message, step_id))

    def error(self, message: str, step_id: Optional[str] = None) -> None:
        self.records.append(ExecutionLogRecord("error", message, step_id))


class TimingCapabilityRouter(CapabilityRouter):
    """A :class:`CapabilityRouter` that times what it dispatches.

    Subclasses the router rather than merely resembling it, so it is one wherever
    one is expected — including to a coordinator that type-checks or to any
    future caller reaching for ``available_capabilities``. Every method delegates
    to the router it wraps; the only thing added is a note of the clock either
    side of ``dispatch``.

    Timings are keyed by ``execution_unit_id``, which the coordinator sets to the
    step id. A step that somehow ran twice would keep its first start and its
    last finish, which is the honest reading of "how long was this step running".
    """

    def __init__(self, inner: CapabilityRouter) -> None:
        # Share the wrapped router's registry rather than copying it, so
        # resolution and availability answer identically to the real thing.
        super().__init__(inner._capabilities)
        self._inner = inner
        self._timings: Dict[str, StepTiming] = {}

    def dispatch(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Dispatch through the wrapped router, noting when it began and ended.

        A step that raises is still timed: the timing is recorded in a ``finally``
        so a failed step is not silently missing from the history that exists to
        explain the failure.
        """
        step_id = request.execution_unit_id
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        try:
            return self._inner.dispatch(request)
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            existing = self._timings.get(step_id)
            self._timings[step_id] = StepTiming(
                started_at=existing.started_at if existing else started_at,
                finished_at=datetime.now(timezone.utc),
                duration_ms=(existing.duration_ms if existing else 0) + elapsed_ms,
            )

    def is_available(self, capability_name: str) -> bool:
        return self._inner.is_available(capability_name)

    def available_capabilities(self) -> List[str]:
        return self._inner.available_capabilities()

    def resolve(self, capability_name: str):
        return self._inner.resolve(capability_name)

    def timing_for(self, step_id: str) -> Optional[StepTiming]:
        """When the named step ran, or ``None`` if it never did."""
        return self._timings.get(step_id)
