"""Pydantic schemas for employee data transfer."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.utils.constants import (
    AutonomyLevel,
    EmployeeAccent,
    EmployeeActivityKind,
    EmployeeCapability,
    EmployeeGlyph,
    EmployeeHealth,
    EmployeePermission,
    EmployeePriority,
    EmployeeStatus,
    EmployeeTone,
    ExecutionMode,
    PermissionLevel,
)


class EmployeeCreate(BaseModel):
    """Input payload for creating an employee.

    ``user_id`` is supplied by the caller (e.g. from the authenticated
    context) and is not part of the client-facing payload.

    Sprint 18.2A added the optional configuration fields. They all have
    defaults, so a Sprint 1D-era payload still creates a valid employee.
    """

    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    language: str = Field(default="en", min_length=2, max_length=50)
    personality: Optional[str] = Field(default=None, max_length=2000)

    autonomy: AutonomyLevel = AutonomyLevel.BALANCED
    tone: EmployeeTone = EmployeeTone.PROFESSIONAL
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    priority: EmployeePriority = EmployeePriority.MEDIUM
    require_approval: bool = True
    accent: EmployeeAccent = EmployeeAccent.SLATE
    glyph: EmployeeGlyph = EmployeeGlyph.BOT
    capabilities: List[EmployeeCapability] = Field(default_factory=list)
    permissions: List["EmployeePermissionInput"] = Field(default_factory=list)


class EmployeeUpdate(BaseModel):
    """Partial update payload. Only supplied fields change.

    ``None`` means "leave alone" for every field, which is why the collections
    default to ``None`` rather than to an empty list — sending ``[]`` clears
    them, omitting them does not.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    language: Optional[str] = Field(default=None, min_length=2, max_length=50)
    personality: Optional[str] = Field(default=None, max_length=2000)

    status: Optional[EmployeeStatus] = None
    autonomy: Optional[AutonomyLevel] = None
    tone: Optional[EmployeeTone] = None
    execution_mode: Optional[ExecutionMode] = None
    priority: Optional[EmployeePriority] = None
    require_approval: Optional[bool] = None
    accent: Optional[EmployeeAccent] = None
    glyph: Optional[EmployeeGlyph] = None
    capabilities: Optional[List[EmployeeCapability]] = None
    permissions: Optional[List["EmployeePermissionInput"]] = None


class EmployeePermissionInput(BaseModel):
    """One permission and the level it is granted at."""

    permission: EmployeePermission
    level: PermissionLevel = PermissionLevel.BLOCKED


class EmployeePermissionResponse(BaseModel):
    """A permission held by an employee."""

    model_config = ConfigDict(from_attributes=True)

    permission: EmployeePermission
    level: PermissionLevel


class EmployeeCapabilityResponse(BaseModel):
    """A capability held by an employee."""

    model_config = ConfigDict(from_attributes=True)

    capability: EmployeeCapability


class EmployeeCapabilityInput(BaseModel):
    """Payload for granting a single capability."""

    capability: EmployeeCapability


class EmployeeResponse(BaseModel):
    """Public representation of an employee.

    Sprint 18.2A extended this additively — every field present before is still
    present and unchanged, so existing consumers keep working.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    role: str
    description: Optional[str] = None
    language: str
    personality: Optional[str] = None
    status: str
    created_at: datetime

    # --- Sprint 18.2A ----------------------------------------------------
    updated_at: Optional[datetime] = None
    autonomy: AutonomyLevel = AutonomyLevel.BALANCED
    tone: EmployeeTone = EmployeeTone.PROFESSIONAL
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    priority: EmployeePriority = EmployeePriority.MEDIUM
    require_approval: bool = True
    accent: EmployeeAccent = EmployeeAccent.SLATE
    glyph: EmployeeGlyph = EmployeeGlyph.BOT
    archived_at: Optional[datetime] = None
    # Derived from stored state by ``app.services.employee_health``; never a
    # measurement. Populated by the service, not by ORM attribute lookup.
    health: EmployeeHealth = EmployeeHealth.UNKNOWN
    capabilities: List[EmployeeCapability] = Field(default_factory=list)
    permissions: List[EmployeePermissionResponse] = Field(default_factory=list)
    assignment_count: int = 0


class EmployeeActivityResponse(BaseModel):
    """One recorded event in an employee's history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EmployeeActivityKind
    summary: str
    sequence: int
    created_at: datetime


class EmployeeAssignmentCreate(BaseModel):
    """Payload for assigning an employee to a piece of work."""

    workflow_id: str = Field(min_length=1, max_length=255)
    workflow_name: str = Field(min_length=1, max_length=255)
    priority: EmployeePriority = EmployeePriority.MEDIUM
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    dependency_summary: Optional[str] = Field(default=None, max_length=2000)


class EmployeeAssignmentResponse(BaseModel):
    """A piece of work an employee is assigned to."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: str
    workflow_name: str
    priority: EmployeePriority
    execution_mode: ExecutionMode
    dependency_summary: Optional[str] = None
    created_at: datetime


class EmployeeHealthResponse(BaseModel):
    """An employee's health and the stored facts behind it."""

    employee_id: uuid.UUID
    status: EmployeeStatus
    health: EmployeeHealth
    reasons: List[str] = Field(default_factory=list)


class EmployeeRestoreRequest(BaseModel):
    """Payload for restoring an archived employee."""

    status: EmployeeStatus = EmployeeStatus.DRAFT


# Deferred annotations: EmployeeCreate/EmployeeUpdate reference
# EmployeePermissionInput before it is defined.
EmployeeCreate.model_rebuild()
EmployeeUpdate.model_rebuild()

