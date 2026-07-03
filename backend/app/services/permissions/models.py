"""Permission framework models (Sprint 11.3 — provider-independent DTOs).

Strongly-typed, provider-independent request/result shapes for permission
checks. They carry only plain data (tool name, argument/metadata dicts, an
approval decision + reason + confirmation flag) so no provider/SDK object is
ever exposed across the permission boundary. No concrete permission logic,
approval flow, HTTP, SDK, or provider code lives here.
"""

from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty tool identifier (whitespace-only fails at 422).
ToolName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class PermissionRequest(BaseModel):
    """A provider-independent request to check permission for a tool call.

    ``tool_name`` selects the tool; ``arguments`` are the intended tool inputs;
    and ``metadata`` carries call-context (e.g. correlation ids) that is not a
    tool argument. Both dicts default to empty so callers may omit them.
    """

    tool_name: ToolName
    arguments: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PermissionResult(BaseModel):
    """A provider-independent result of a permission check (immutable).

    ``frozen=True`` makes instances immutable, so a decision cannot be mutated
    after a provider returns it. ``approved`` is the decision; ``reason``
    optionally explains it; ``requires_user_confirmation`` signals that a future
    approval flow must confirm with the user before proceeding.
    """

    model_config = ConfigDict(frozen=True)

    approved: bool
    reason: Optional[str] = None
    requires_user_confirmation: bool = False
