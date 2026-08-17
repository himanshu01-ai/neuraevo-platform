"""Fixed-window rate limiting for sensitive endpoints (Sprint 18.1A).

Deliberately small: an in-process, thread-safe fixed-window counter with a
provider-style seam so a shared backend (Redis) can replace it later without
touching callers.

LIMITATION: counters live in the worker process, so with multiple workers the
effective limit is ``limit x workers``. That is an acceptable brute-force
speed bump for now, not a distributed guarantee — a shared store is required
before horizontal scaling. Routers depend on :class:`RateLimiter`, never on
this implementation.
"""

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of a rate-limit check."""

    allowed: bool
    retry_after_seconds: int = 0


class RateLimiter(ABC):
    """Replaceable rate-limiting strategy."""

    @abstractmethod
    def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        """Record an attempt against ``key`` and report whether it is allowed."""

    @abstractmethod
    def reset(self, key: str) -> None:
        """Clear the counter for ``key`` (e.g. after a successful login)."""


class InMemoryRateLimiter(RateLimiter):
    """Thread-safe fixed-window counter held in process memory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key -> (window_started_at, attempts)
        self._windows: dict[str, tuple[float, int]] = {}

    def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.monotonic()
        with self._lock:
            started_at, attempts = self._windows.get(key, (now, 0))

            # Start a fresh window once the previous one has elapsed.
            if now - started_at >= window_seconds:
                started_at, attempts = now, 0

            attempts += 1
            self._windows[key] = (started_at, attempts)

            if attempts > limit:
                remaining = window_seconds - (now - started_at)
                return RateLimitDecision(
                    allowed=False, retry_after_seconds=max(1, int(remaining) + 1)
                )
            return RateLimitDecision(allowed=True)

    def reset(self, key: str) -> None:
        with self._lock:
            self._windows.pop(key, None)


class NullRateLimiter(RateLimiter):
    """Allows everything. Used when rate limiting is disabled."""

    def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        return RateLimitDecision(allowed=True)

    def reset(self, key: str) -> None:
        return None
