"""Data-access layer for :class:`~app.models.workflow.Workflow`.

Persistence only — no business logic, no ownership checks, no lifecycle
decisions. Transaction control is left to the caller; methods ``flush`` so
generated values like ``id`` are populated.

Unlike employees there is no soft delete: a workflow owns no memories,
sessions or history that must outlive it, so ``delete`` removes the row.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow import Workflow


class WorkflowRepository:
    """CRUD-style accessors for :class:`Workflow` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Reads -----------------------------------------------------------

    def get_by_id(self, workflow_id: uuid.UUID) -> Optional[Workflow]:
        return self.session.get(Workflow, workflow_id)

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Workflow]:
        stmt = (
            select(Workflow)
            .where(Workflow.user_id == user_id)
            .order_by(Workflow.created_at)
            .offset(skip)
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def count_by_name(
        self,
        user_id: uuid.UUID,
        name: str,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> int:
        """How many of this user's workflows already use ``name``."""
        stmt = select(Workflow).where(
            Workflow.user_id == user_id, Workflow.name == name
        )
        if exclude_id is not None:
            stmt = stmt.where(Workflow.id != exclude_id)
        return len(self.session.scalars(stmt).all())

    # --- Writes ----------------------------------------------------------

    def create(
        self,
        user_id: uuid.UUID,
        *,
        name: str,
        description: Optional[str],
        graph: Dict[str, Any],
        status: str,
    ) -> Workflow:
        """Persist a new workflow owned by ``user_id``.

        Takes primitives rather than the create schema: duplication builds a
        row from an existing workflow, not from a request body, and both paths
        should land in the same place.
        """
        workflow = Workflow(
            user_id=user_id,
            name=name,
            description=description,
            graph=graph,
            status=status,
        )
        self.session.add(workflow)
        self.session.flush()
        self.session.refresh(workflow)
        return workflow

    def update_fields(self, workflow: Workflow, **fields: object) -> Workflow:
        """Assign the supplied attributes. The caller decides which to send."""
        for key, value in fields.items():
            setattr(workflow, key, value)
        self.session.flush()
        return workflow

    def set_status(
        self,
        workflow: Workflow,
        status: str,
        *,
        archived_at: Optional[datetime] = None,
    ) -> Workflow:
        workflow.status = status
        workflow.archived_at = archived_at
        self.session.flush()
        return workflow

    def delete(self, workflow: Workflow) -> None:
        self.session.delete(workflow)
        self.session.flush()
