"""Pydantic schemas for Task Engine data transfer (Sprint 19).

The ORM model is never exposed: every endpoint speaks in these types. A task's
references cross the wire as small nested refs — id plus the display facts the
UI needs — rather than as full employee or workflow documents, which their own
domains already serve.

Execution shapes are **reused**, not redefined: a run a task launched is the
same recorded run the workflow API serves, so it answers in the same
``WorkflowExecutionSummaryResponse`` / ``WorkflowExecutionResponse`` shapes.
Two DTOs for one fact would be the duplication this sprint exists to avoid.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.workflow import WorkflowExecutionSummaryResponse
from app.utils.constants import (
    EmployeePriority,
    TaskExecutionMode,
    TaskStatus,
    WorkflowStatus,
)


class TaskCreate(BaseModel):
    """Input payload for creating a task.

    ``user_id`` is taken from the authenticated context, never from the client.
    The workflow and employee are optional — a task can be described first and
    shaped or assigned later, which is how the builder behaves.
    """

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: EmployeePriority = EmployeePriority.MEDIUM
    execution_mode: TaskExecutionMode = TaskExecutionMode.MANUAL
    workflow_id: Optional[uuid.UUID] = None
    employee_id: Optional[uuid.UUID] = None


class TaskUpdate(BaseModel):
    """Partial update payload. Only supplied fields change.

    For ``workflow_id`` and ``employee_id`` an explicit ``null`` *clears* the
    reference, while omitting the field leaves it alone — the service reads
    ``model_fields_set`` to tell the two apart, exactly as the employee domain
    does with ``exclude_unset``.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[EmployeePriority] = None
    execution_mode: Optional[TaskExecutionMode] = None
    workflow_id: Optional[uuid.UUID] = None
    employee_id: Optional[uuid.UUID] = None


class TaskCommandRequest(BaseModel):
    """A requested state change: queue, pause, resume, cancel, or retry.

    A plain string validated by the service against its one command table,
    rather than an enum here — the table also depends on the task's current
    state, so the schema can't be the judge of legality anyway.
    """

    command: str = Field(min_length=1, max_length=20)


class TaskExecuteRequest(BaseModel):
    """Optional seed inputs for the launched run, as the workflow API takes."""

    inputs: Dict[str, Any] = Field(default_factory=dict)


class TaskDuplicateRequest(BaseModel):
    """Payload for duplicating a task. Omitting ``name`` derives one."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class TaskEmployeeRef(BaseModel):
    """The assignee, as identity plus the display facts the task UI shows."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class TaskWorkflowRef(BaseModel):
    """The attached workflow: identity, name, and its lifecycle status.

    The status rides along so the task screen can say whether the workflow is
    runnable without a second request — displaying it is this sprint's
    "task displays workflow status" requirement.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: WorkflowStatus


class TaskResponse(BaseModel):
    """A task in full, with its references resolved for display.

    ``latest_execution`` is the newest run this task launched, in the shape
    history already answers in; ``execution_count`` is how many there have
    been. Both carried so the task screen reflects execution results without
    fetching history separately.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    business_id: str
    name: str
    description: Optional[str] = None
    status: TaskStatus
    priority: EmployeePriority
    execution_mode: TaskExecutionMode
    progress: int
    workflow: Optional[TaskWorkflowRef] = None
    assignee: Optional[TaskEmployeeRef] = None
    latest_execution: Optional[WorkflowExecutionSummaryResponse] = None
    execution_count: int = 0
    created_at: datetime
    updated_at: datetime


class TaskExecutionListResponse(BaseModel):
    """A page of the runs a task launched, with the total behind it.

    The items are the workflow domain's own history summaries — a task's run
    *is* a workflow run, so it lists in the same shape.
    """

    items: list[WorkflowExecutionSummaryResponse] = Field(default_factory=list)
    total: int
