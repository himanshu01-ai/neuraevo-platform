"""Pydantic schemas for the runtime AI context (Sprint 7.1 AI Context Engine).

Assembles everything an AI generation step needs *at runtime* — the employee,
its blueprint, memories, recent conversation history, a (stub) permission
profile, language, personality, and the current user input — into a single
structure.

This is intentionally distinct from the Sprint 6C ``AIContextResponse`` (which
feeds the conversation prompt pipeline) and does not replace it. These are
read-only DTOs: no AI, no prompt building, no persistence. Existing response
schemas are reused as building blocks so no fields are duplicated.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.blueprint import BlueprintResponse
from app.schemas.conversation_context import ConversationContextResponse
from app.schemas.employee import EmployeeResponse
from app.schemas.memory_context import MemoryContextResponse


class PermissionProfile(BaseModel):
    """Placeholder permission profile (stub).

    Sprint 7.1 does **not** implement permission execution. This stub carries
    safe, deny-by-default values so the runtime context has a stable shape that
    a later permissions sprint can populate without changing any consumer.
    """

    can_use_tools: bool = False
    can_write_memory: bool = False
    allowed_tools: List[str] = Field(default_factory=list)


class RuntimeAIContext(BaseModel):
    """Complete runtime context assembled before any AI generation.

    ``language`` and ``personality`` are surfaced at the top level for
    convenience (mirroring the employee's fields). ``recent_conversation``
    carries the conversation history as assembled by the existing conversation
    context service; the recency window is owned by that service.
    """

    employee: EmployeeResponse
    blueprint: BlueprintResponse
    memories: MemoryContextResponse
    recent_conversation: ConversationContextResponse
    permission_profile: PermissionProfile
    language: str
    personality: Optional[str] = None
    current_user_input: str
