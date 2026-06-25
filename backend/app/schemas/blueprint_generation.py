"""Pydantic schemas for blueprint generation (preview/foundation).

These describe the aggregated interview context, the constructed prompt, and a
generated draft blueprint. Sprint 4A is a non-persisting preview: no AI
provider is called and nothing is written to the database.
"""

import uuid
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BlueprintFieldSet(BaseModel):
    """The six free-text blueprint fields, all optional."""

    vision: Optional[str] = None
    communication_style: Optional[str] = None
    personality_traits: Optional[str] = None
    goals: Optional[str] = None
    constraints: Optional[str] = None
    preferences: Optional[str] = None


class InterviewQAItem(BaseModel):
    """A single question paired with its answer (if any)."""

    question_id: uuid.UUID
    question_order: int
    question_text: str
    answer_text: Optional[str] = None
    answered: bool


class BlueprintGenerationContext(BaseModel):
    """Aggregated, AI-ready context assembled from interview data."""

    employee_id: uuid.UUID
    blueprint_id: uuid.UUID
    employee_name: str
    role: str
    language: str
    personality: Optional[str] = None
    existing_blueprint: BlueprintFieldSet
    qa_items: List[InterviewQAItem]
    total_questions: int
    answered_count: int
    completeness: float = Field(ge=0.0, le=1.0)


class GeneratedBlueprintDraft(BlueprintFieldSet):
    """A draft blueprint produced by the generator (not persisted)."""


class GenerationMetadata(BaseModel):
    """Provenance for a generation run."""

    provider: str
    model: Optional[str] = None
    deterministic: bool
    persisted: bool = False


class BlueprintGenerationPreviewResponse(BaseModel):
    """Full preview payload: context, prompt, draft, and metadata."""

    model_config = ConfigDict(from_attributes=True)

    employee_id: uuid.UUID
    blueprint_id: uuid.UUID
    context: BlueprintGenerationContext
    prompt: str
    draft: GeneratedBlueprintDraft
    metadata: GenerationMetadata
    warnings: List[str] = Field(default_factory=list)
