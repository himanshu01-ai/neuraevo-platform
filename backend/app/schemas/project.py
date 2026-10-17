"""Validated inputs for project and checkpoint domain services."""

import uuid
from typing import Optional

from pydantic import BaseModel, Field


ProjectText = Optional[str]


class ProjectCreate(BaseModel):
    """Create an unapproved project workspace."""

    name: str = Field(min_length=1, max_length=255)
    objective: ProjectText = Field(default=None, max_length=10000)
    technology_stack: ProjectText = Field(default=None, max_length=10000)
    repository_reference: ProjectText = Field(default=None, max_length=2048)
    constraints: ProjectText = Field(default=None, max_length=10000)
    current_state: ProjectText = Field(default=None, max_length=10000)


class ProjectMetadataUpdate(BaseModel):
    """Rename a project without changing its approved context."""

    name: str = Field(min_length=1, max_length=255)
    expected_version: int = Field(ge=1)


class ProjectContextReplacement(BaseModel):
    """A complete, explicitly approved replacement of project context."""

    objective: str = Field(min_length=1, max_length=10000)
    technology_stack: ProjectText = Field(default=None, max_length=10000)
    repository_reference: ProjectText = Field(default=None, max_length=2048)
    constraints: ProjectText = Field(default=None, max_length=10000)
    current_state: ProjectText = Field(default=None, max_length=10000)
    expected_version: int = Field(ge=1)
    approved: bool = False


class ProjectLifecycleChange(BaseModel):
    """Optimistic-concurrency input for archive or restore."""

    expected_version: int = Field(ge=1)


class ProjectCheckpointCreate(BaseModel):
    """One explicit request to preserve a complete resume snapshot."""

    decisions: ProjectText = Field(default=None, max_length=10000)
    verified_progress: ProjectText = Field(default=None, max_length=10000)
    verification_note: ProjectText = Field(default=None, max_length=10000)
    next_steps: ProjectText = Field(default=None, max_length=10000)
    source_message_id: Optional[uuid.UUID] = None
    request_id: uuid.UUID
    expected_version: int = Field(ge=1)
    confirmed: bool = False

