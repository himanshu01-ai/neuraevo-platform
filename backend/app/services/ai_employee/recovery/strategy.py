"""Retry strategy (Sprint 16.8 — deterministic next-retry tick math, no timers).

Defines :class:`RetryStrategy`, the deterministic component that computes *when* a
failed workflow should be retried, expressed as an integer *tick*. It supports the
four strategies — ``IMMEDIATE`` (now), ``DELAYED`` (now + base), ``FIXED_INTERVAL``
(now + base each attempt), and ``EXPONENTIAL_BACKOFF`` (now + base·2^attempt).

There is no timer, wall-clock, or sleep dependency: the "now" tick is supplied by
the caller and all arithmetic is pure and deterministic — the same inputs always
yield the same tick. It holds no state and executes nothing. Strictly additive to
Sprints 1.x–16.7.
"""

from app.services.ai_employee.recovery.models import RetryStrategyType


class RetryStrategy:
    """Computes deterministic next-retry ticks (no timers, no execution).

    Constructed with a :class:`RetryStrategyType` and a ``base_delay`` (ticks).
    ``next_retry`` computes the retry tick from a caller-supplied ``now_tick`` and
    the failed ``attempt`` number — ``IMMEDIATE`` returns now; ``DELAYED`` and
    ``FIXED_INTERVAL`` add the base delay; ``EXPONENTIAL_BACKOFF`` adds the base
    delay doubled per attempt. Stateless; same inputs in -> same tick out.
    """

    def __init__(
        self,
        strategy_type: RetryStrategyType = RetryStrategyType.IMMEDIATE,
        base_delay: int = 1,
    ) -> None:
        self.strategy_type = strategy_type
        self.base_delay = max(base_delay, 0)

    def next_retry(self, now_tick: int, attempt: int) -> int:
        """Return the deterministic retry tick for ``attempt`` relative to ``now_tick``."""
        strategy = self.strategy_type
        if strategy == RetryStrategyType.IMMEDIATE:
            return now_tick
        if strategy == RetryStrategyType.DELAYED:
            return now_tick + self.base_delay
        if strategy == RetryStrategyType.FIXED_INTERVAL:
            return now_tick + self.base_delay
        if strategy == RetryStrategyType.EXPONENTIAL_BACKOFF:
            return now_tick + self.base_delay * (2 ** max(attempt, 0))
        return now_tick
