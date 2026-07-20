"""Data-access layer for workflow execution history (Sprint 18.10).

Persistence only — no ownership checks, no lifecycle decisions, no business
rules. Transaction control is left to the caller; methods ``flush`` so generated
values like ``id`` are populated, matching :class:`WorkflowRepository`.

There is no ``update`` and no ``delete`` here, and that is the point: history is
written once and never revised. A retry adds a row; it does not touch the row it
repeats. Rows go only when their workflow does, by cascade.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.workflow_execution import (
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowExecutionStep,
)


class WorkflowExecutionRepository:
    """CRUD-style accessors for execution history rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Reads -----------------------------------------------------------

    def get_by_id(self, execution_id: uuid.UUID) -> Optional[WorkflowExecution]:
        """One execution, without its steps or logs."""
        return self.session.get(WorkflowExecution, execution_id)

    def get_with_detail(self, execution_id: uuid.UUID) -> Optional[WorkflowExecution]:
        """One execution with its steps and logs already loaded.

        Eager-loaded because the detail view always renders all three, and
        lazy-loading them would turn one read into three round trips per request.
        """
        stmt = (
            select(WorkflowExecution)
            .where(WorkflowExecution.id == execution_id)
            .options(
                selectinload(WorkflowExecution.steps),
                selectinload(WorkflowExecution.logs),
            )
        )
        return self.session.scalars(stmt).first()

    def list_by_workflow(
        self,
        workflow_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[WorkflowExecution]:
        """A workflow's runs, newest first.

        Steps and logs are deliberately not loaded: a history list shows the
        summary of each run, and pulling every step of every run to render it
        would be the most expensive way to answer the cheapest question.
        """
        stmt = (
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .order_by(WorkflowExecution.started_at.desc(), WorkflowExecution.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def count_by_workflow(self, workflow_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
        )
        return int(self.session.scalar(stmt) or 0)

    # --- Writes ----------------------------------------------------------

    def add(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Persist one finished run, with whatever steps and logs it carries."""
        self.session.add(execution)
        self.session.flush()
        return execution

    def add_step(self, step: WorkflowExecutionStep) -> WorkflowExecutionStep:
        self.session.add(step)
        self.session.flush()
        return step

    def add_log(self, log: WorkflowExecutionLog) -> WorkflowExecutionLog:
        self.session.add(log)
        self.session.flush()
        return log
