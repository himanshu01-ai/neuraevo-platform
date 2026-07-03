"""Tool framework models (Sprint 11.1 — provider-independent DTOs).

Strongly-typed, provider-independent request/result shapes for tool execution.
They intentionally carry only plain data (names, argument/metadata dicts,
output/error/timing) so no provider/SDK object is ever exposed across the tool
boundary. No concrete tool, HTTP, SDK, or provider logic lives here.
"""

from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty tool identifier (whitespace-only fails at 422).
ToolName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class ToolExecutionRequest(BaseModel):
    """A provider-independent request to execute a single tool.

    ``tool_name`` selects the tool; ``arguments`` are the tool inputs; and
    ``metadata`` carries call-context (e.g. correlation ids) that is not a tool
    argument. Both dicts default to empty so callers may omit them.
    """

    tool_name: ToolName
    arguments: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    """A provider-independent result of a tool execution (immutable).

    ``frozen=True`` makes instances immutable, so a result cannot be mutated
    after a provider returns it. ``output`` holds plain result data (never a
    provider/SDK object); ``error`` describes a failure; ``execution_time_ms``
    is optional timing.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
