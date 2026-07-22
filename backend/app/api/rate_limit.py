"""Per-user rate limiting for the expensive AI endpoints (Sprint 25).

Reuses the auth rate limiter's abstraction (``RateLimiter`` + ``RateLimitDecision``)
rather than inventing a second one, so there is one limiter model across the
platform. It caps how often a single user may hit the AI/generation endpoints,
which are the costly ones — a bound on abuse and runaway cost, not a throttle on
normal use: the defaults are deliberately generous, and the whole thing is off
when ``AI_RATE_LIMIT_ENABLED`` is false.

A refusal is the platform's standard error: ``429`` with the one
``{"detail": ...}`` contract and a ``Retry-After`` header, exactly like the auth
endpoints' limiter.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.rate_limiter import (
    InMemoryRateLimiter,
    NullRateLimiter,
    RateLimiter,
)

# Process-wide singleton: rate-limit counters must outlive a request, exactly as
# the auth limiter is a module-level singleton. In-process only — the same
# multi-worker caveat as the auth limiter applies (see rate_limiter.py).
_ai_rate_limiter: RateLimiter = (
    InMemoryRateLimiter() if settings.AI_RATE_LIMIT_ENABLED else NullRateLimiter()
)


def get_ai_rate_limiter() -> RateLimiter:
    """Provide the process-wide AI rate limiter."""
    return _ai_rate_limiter


def enforce_ai_rate_limit(
    current_user: Annotated[User, Depends(get_current_user)],
    limiter: Annotated[RateLimiter, Depends(get_ai_rate_limiter)],
) -> None:
    """Reject the request with 429 when the user has exceeded the AI budget.

    Keyed per user (never per IP): the limit protects the platform from one
    account's overuse and is unaffected by shared networks. Runs as a route
    dependency, so ``get_current_user`` has already authenticated the caller and
    the same instance is reused (no second decode).
    """
    decision = limiter.check(
        f"ai:{current_user.id}",
        limit=settings.AI_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
