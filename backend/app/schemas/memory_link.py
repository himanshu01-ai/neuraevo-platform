"""Pydantic schemas for memory integration (linking + user-wide reads).

The Sprint 2 :class:`~app.schemas.memory.MemoryResponse` is reused wherever the
existing employee-scoped shape fits. These types add only what integration
needs: a request body that names the memory to link, and a response that carries
a memory alongside its owning employee's *name* — because the shared-resource
list and the linked-memory lists show memories from many employees, and a bare
``employee_id`` would make the UI resolve every owner itself.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.utils.constants import MemoryType


class MemoryLinkCreate(BaseModel):
    """Request body naming the existing memory to reference.

    The task or workflow comes from the path; only the memory id is in the body.
    A link references a memory that already exists — nothing here creates memory
    content.
    """

    memory_id: uuid.UUID


class UserMemoryResponse(BaseModel):
    """A memory with its owning employee's name, for cross-employee views.

    A superset of :class:`MemoryResponse` (same real columns) plus
    ``employee_name``, used by the user-wide list/search and the linked-memory
    lists — all of which surface memories from more than one employee. Built
    explicitly from ``(Memory, name)`` rows rather than by ORM attribute
    validation, so the join's name rides along without a relationship.
    """

    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    memory_type: MemoryType
    content: str
    importance_score: float
    created_at: datetime


class UserMemoryListResponse(BaseModel):
    """A page of a user's memories with the total behind it."""

    items: list[UserMemoryResponse] = Field(default_factory=list)
    total: int
