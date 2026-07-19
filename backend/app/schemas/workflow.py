"""Pydantic schemas for workflow data transfer.

The ORM model is never exposed: every endpoint speaks in these types, so the
wire contract stays independent of how a workflow is stored. The graph crosses
the boundary as a plain JSON object — its *structure* is checked by
``app.services.workflow_graph`` at the service layer, which is where the one
set of rules lives.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.utils.constants import WorkflowStatus


class WorkflowCreate(BaseModel):
    """Input payload for creating a workflow.

    ``user_id`` is taken from the authenticated context, never from the client.
    ``graph`` is optional so a workflow can be created as a blank canvas and
    drawn afterwards, which is how the builder's "new workflow" flow behaves.
    """

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    graph: Optional[Dict[str, Any]] = None


class WorkflowUpdate(BaseModel):
    """Partial update payload. Only supplied fields change.

    ``None`` means "leave alone" for every field. ``status`` is accepted here so
    publishing is an ordinary update rather than a bespoke endpoint, but the
    transition is still checked against ``workflow_lifecycle``.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    graph: Optional[Dict[str, Any]] = None
    status: Optional[WorkflowStatus] = None


class WorkflowRestoreRequest(BaseModel):
    """Payload for restoring an archived workflow."""

    status: WorkflowStatus = WorkflowStatus.DRAFT


class WorkflowDuplicateRequest(BaseModel):
    """Payload for duplicating a workflow.

    The name is optional: omitting it lets the service derive one, so the
    common case is a bodyless request.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class WorkflowSummaryResponse(BaseModel):
    """A workflow without its graph — what a list needs.

    The graph is the large part of the document and no list renders it, so it
    is left out rather than sent once per row.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: WorkflowStatus
    node_count: int
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkflowResponse(WorkflowSummaryResponse):
    """A workflow in full, including the authored graph."""

    graph: Dict[str, Any]
