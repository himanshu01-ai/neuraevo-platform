"""Response builder (Sprint 16.10 — produce stable, provider-independent responses).

Defines :class:`ResponseBuilder`, which produces the Service Layer's stable response
contracts from plain inputs. Submission outcomes use ``success``/``failure``; task
status uses ``running``/``completed``/``failed``/``cancelled``/``paused`` plus the
``not_found``/``errored`` reads. Every response is an immutable, provider-independent
DTO — no provider/SDK object and no raw exception ever appears in a response.

It is deterministic and stateless: it builds DTOs only and decides, delegates, and
executes nothing. It never touches the Workflow Coordinator, a capability, a
repository, a database, an LLM provider, a thread, or the network. Strictly additive
to Sprints 1.x–16.9, whose modules are left untouched.
"""

from typing import Any, Dict, Optional

from app.services.ai_employee.service.models import (
    ServiceError,
    TaskState,
    TaskStatusResponse,
    TaskSubmissionResponse,
)


class ResponseBuilder:
    """Builds stable service responses (deterministic, provider-independent).

    Submission: ``success`` (accepted) and ``failure`` (rejected). Status:
    ``running``, ``completed``, ``failed``, ``cancelled``, ``paused`` (built over the
    shared :meth:`status`), plus ``not_found`` and ``errored`` for reads that carry a
    :class:`ServiceError`. Stateless; it builds DTOs only.
    """

    # --- submission ------------------------------------------------------
    def success(
        self,
        request_id: str,
        task_id: str,
        state: TaskState,
        session_id: Optional[str],
        idempotent: bool = False,
    ) -> TaskSubmissionResponse:
        """Build an accepted :class:`TaskSubmissionResponse`."""
        return TaskSubmissionResponse(
            request_id=request_id,
            task_id=task_id,
            accepted=True,
            state=state,
            session_id=session_id,
            idempotent=idempotent,
        )

    def failure(
        self,
        request_id: str,
        error: ServiceError,
        task_id: str = "",
    ) -> TaskSubmissionResponse:
        """Build a rejected :class:`TaskSubmissionResponse` carrying ``error``."""
        return TaskSubmissionResponse(
            request_id=request_id,
            task_id=task_id,
            accepted=False,
            state=None,
            error=error,
        )

    # --- status ----------------------------------------------------------
    def status(
        self,
        task_id: str,
        state: TaskState,
        session_id: Optional[str] = None,
        result_summary: Optional[Dict[str, Any]] = None,
        response_metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskStatusResponse:
        """Build a :class:`TaskStatusResponse` for ``task_id`` in ``state``."""
        return TaskStatusResponse(
            task_id=task_id,
            state=state,
            success=state == TaskState.COMPLETED,
            session_id=session_id,
            detail=state.value,
            result_summary=dict(result_summary or {}),
            response_metadata=dict(response_metadata or {}),
        )

    def running(self, task_id: str, session_id=None, result_summary=None):
        """Build a ``RUNNING`` status response."""
        return self.status(
            task_id, TaskState.RUNNING, session_id, result_summary
        )

    def completed(self, task_id: str, session_id=None, result_summary=None):
        """Build a ``COMPLETED`` status response."""
        return self.status(
            task_id, TaskState.COMPLETED, session_id, result_summary
        )

    def failed(self, task_id: str, session_id=None, result_summary=None):
        """Build a ``FAILED`` status response."""
        return self.status(
            task_id, TaskState.FAILED, session_id, result_summary
        )

    def cancelled(
        self,
        task_id: str,
        session_id=None,
        result_summary=None,
        response_metadata=None,
    ):
        """Build a ``CANCELLED`` status response."""
        return self.status(
            task_id,
            TaskState.CANCELLED,
            session_id,
            result_summary,
            response_metadata,
        )

    def paused(
        self,
        task_id: str,
        session_id=None,
        result_summary=None,
        response_metadata=None,
    ):
        """Build a ``PAUSED`` status response."""
        return self.status(
            task_id,
            TaskState.PAUSED,
            session_id,
            result_summary,
            response_metadata,
        )

    # --- error reads -----------------------------------------------------
    def errored(
        self,
        task_id: str,
        state: Optional[TaskState],
        session_id: Optional[str],
        error: ServiceError,
    ) -> TaskStatusResponse:
        """Build a status response that carries ``error`` (state left unchanged)."""
        return TaskStatusResponse(
            task_id=task_id,
            state=state,
            success=False,
            session_id=session_id,
            detail=error.code.value,
            error=error,
        )

    def not_found(
        self, task_id: str, error: ServiceError
    ) -> TaskStatusResponse:
        """Build a not-found status response carrying ``error`` (no state)."""
        return TaskStatusResponse(
            task_id=task_id,
            state=None,
            success=False,
            detail=error.code.value,
            error=error,
        )
