"""Pydantic schemas for employee data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    """Input payload for creating an employee.

    ``user_id`` is supplied by the caller (e.g. from the authenticated
    context) and is not part of the client-facing payload.
    """

    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class EmployeeResponse(BaseModel):
    """Public representation of an employee."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    role: str
    description: Optional[str] = None
    status: str
    created_at: datetime
