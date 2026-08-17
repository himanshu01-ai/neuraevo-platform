"""Recovery manager (Sprint 16.2 — recovery abstraction + basic policy).

Defines the :class:`RecoveryManager` abstraction and its basic implementation
:class:`BasicRecoveryManager`. The abstraction lets later Sprint 16.x policies
(backoff, per-capability, partial replay) plug in behind ``can_retry``/``retry``/
``abort`` without any change to the lifecycle manager. The basic policy allows a
bounded number of whole-job retries and no more.

A retry deterministically moves a ``FAILED`` job back to ``RUNNING`` and
increments the attempt counter; an abort moves it to a terminal ``CANCELLED``.
There is no advanced recovery policy here — no partial-step replay, no backoff, no
scheduling. Stateless and deterministic; it produces new immutable
:class:`WorkflowInstance` states and executes nothing. Strictly additive to
Sprints 1.x–16.1.
"""

from abc import ABC, abstractmethod

from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowLifecycleStatus,
)


class RecoveryManager(ABC):
    """Abstraction for retrying or aborting a failed delegated job (no execution).

    A policy decides whether a :class:`WorkflowInstance` ``can_retry``, produces a
    ``retry`` instance (a new ``RUNNING`` state), and produces an ``abort``
    instance (a new terminal ``CANCELLED`` state). Implementations must be
    deterministic and must not execute, resume, or re-plan anything — they only
    transform the instance's lifecycle state.
    """

    @abstractmethod
    def can_retry(self, instance: WorkflowInstance) -> bool:
        """Return whether ``instance`` is eligible to be retried."""

    @abstractmethod
    def retry(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Return a new ``RUNNING`` instance with the attempt counter advanced."""

    @abstractmethod
    def abort(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Return a new terminal ``CANCELLED`` instance."""


class BasicRecoveryManager(RecoveryManager):
    """Basic recovery policy — a bounded number of whole-job retries, then stop.

    ``can_retry`` is ``True`` only while the job is ``FAILED`` and its attempt
    counter is below ``max_attempts`` (default 1). ``retry`` moves a failed job
    back to ``RUNNING`` and increments the attempt counter; ``abort`` moves the job
    to a terminal ``CANCELLED``. No backoff, partial replay, or scheduling.
    Deterministic; it produces new immutable instances and executes nothing.
    """

    def __init__(self, max_attempts: int = 1) -> None:
        self.max_attempts = max_attempts

    def can_retry(self, instance: WorkflowInstance) -> bool:
        """Return whether the failed ``instance`` still has retries remaining."""
        state = instance.lifecycle_state
        return (
            state.status == WorkflowLifecycleStatus.FAILED
            and state.attempt < self.max_attempts
        )

    def retry(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Return a ``RUNNING`` instance with the attempt counter incremented.

        Assumes ``can_retry`` holds (the lifecycle manager checks it first). Moves
        the lifecycle state from ``FAILED`` to ``RUNNING`` and advances ``attempt``
        by one; nothing is executed or re-planned.
        """
        new_state = instance.lifecycle_state.transition_to(
            WorkflowLifecycleStatus.RUNNING,
            attempt=instance.lifecycle_state.attempt + 1,
        )
        return instance.model_copy(update={"lifecycle_state": new_state})

    def abort(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Return a terminal ``CANCELLED`` instance (recovery gives up)."""
        new_state = instance.lifecycle_state.transition_to(
            WorkflowLifecycleStatus.CANCELLED, terminal=True
        )
        return instance.model_copy(update={"lifecycle_state": new_state})
