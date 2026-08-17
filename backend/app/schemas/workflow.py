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


# =====================================================================
# Execution (Sprint 18.6)
# =====================================================================
#
# These are the API's own shapes, deliberately separate from the runtime's
# ``WorkflowExecutionResult`` and its nested models. The runtime types stay
# behind the service boundary; the router maps a result into these so a change
# to the runtime's internals never reshapes the wire contract.


class WorkflowExecuteRequest(BaseModel):
    """Optional seed inputs for a run, exposed to steps as ``input.<key>``.

    The builder sends nothing today, so this defaults to empty and a bodyless
    ``POST`` runs the workflow as authored.
    """

    inputs: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionStepResponse(BaseModel):
    """One step's outcome within a run."""

    step_id: str
    capability: str
    status: str
    outputs: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResponse(BaseModel):
    """The structured result of running a workflow.

    ``status`` is the run's terminal state (``COMPLETED`` / ``FAILED``). A run
    that fails a step is still a *successful call*: the endpoint returns 200
    with ``status="FAILED"`` and ``failed_step_id`` set. Rejections — not owner,
    not published, untranslatable — are the 4xx paths and never reach here.

    Sprint 18.10 added ``execution_id``, ``started_at``, ``finished_at`` and
    ``duration_ms``. Additive only: every field that was here before is still
    here, unchanged, so an existing caller reads this exactly as it did.
    """

    workflow_id: uuid.UUID
    #: The run's own identity, and the handle for looking it up again.
    execution_id: uuid.UUID
    status: str
    completed_step_count: int
    total_step_count: int
    failed_step_id: Optional[str] = None
    steps: list[WorkflowExecutionStepResponse] = Field(default_factory=list)
    final_outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int


# =====================================================================
# Execution history (Sprint 18.10)
# =====================================================================
#
# A run is no longer only an answer to a request — it is a record that outlives
# it. These are the shapes that record is read back in: a summary per row of
# history, and a detail carrying the steps and log the summary omits.


class WorkflowExecutionSummaryResponse(BaseModel):
    """One past run, as a history list shows it.

    Steps, outputs and logs are left out on purpose: a list renders none of
    them, and a workflow with a hundred runs would otherwise carry every step of
    every one of them to draw a table.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    total_step_count: int
    completed_step_count: int
    failed_step_id: Optional[str] = None
    error: Optional[str] = None
    #: ``manual`` or ``retry``.
    trigger: str
    #: The run this one repeats, when it is a retry.
    retry_of_execution_id: Optional[uuid.UUID] = None


class WorkflowExecutionListResponse(BaseModel):
    """A page of a workflow's history, with the total behind it."""

    items: list[WorkflowExecutionSummaryResponse] = Field(default_factory=list)
    total: int


class WorkflowExecutionStepRecordResponse(BaseModel):
    """What one step did, as history kept it.

    Richer than the step in a live result: it carries the timings the runtime
    does not produce, and the metadata and artifact descriptors the live
    response has always discarded.
    """

    model_config = ConfigDict(from_attributes=True)

    step_id: str
    capability: str
    status: str
    position: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    outputs: Dict[str, Any] = Field(default_factory=dict)
    step_metadata: Dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Dict[str, Any]] = Field(default_factory=list)


class WorkflowExecutionLogResponse(BaseModel):
    """One structured line of a run's account.

    ``message`` is written for a person. No traceback, exception type or
    internal identifier reaches this field.
    """

    model_config = ConfigDict(from_attributes=True)

    sequence: int
    level: str
    message: str
    step_id: Optional[str] = None


class WorkflowExecutionDetailResponse(WorkflowExecutionSummaryResponse):
    """One past run in full: what each step did, and what was said about it."""

    steps: list[WorkflowExecutionStepRecordResponse] = Field(default_factory=list)
    logs: list[WorkflowExecutionLogResponse] = Field(default_factory=list)
