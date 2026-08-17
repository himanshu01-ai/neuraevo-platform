"""Memory Orchestrator models (Sprint 16.6 — immutable memory DTOs + errors).

Provider-independent, immutable DTOs, the category/importance enums, and the
deterministic error for the Memory Orchestrator: the memory record, the policy
decision, the deterministic query, and the aggregated summary. Memory *decides
what to remember and retrieve*; storage stays in the Persistence Layer.

These carry only plain data — never a provider/SDK object, and never a live
policy/classifier/retriever object crosses the boundary. All timing is a
deterministic integer sequence (never a clock). There is no embedding, no vector,
no semantic search, and no LLM here. Strictly additive to Sprints 1.x–16.5, whose
modules are left untouched.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class MemoryLayerError(Exception):
    """Base class for the Memory Orchestrator's deterministic errors."""


class MemoryNotFoundError(MemoryLayerError):
    """Raised when an update targets a memory id that is not remembered."""


class MemoryCategory(str, Enum):
    """The allowed, deterministic memory categories (the memory types).

    ``USER_PREFERENCE`` — a stated user preference. ``WORKFLOW`` — workflow state or
    progress. ``TASK_RESULT`` — the outcome of delegated work. ``APPROVAL`` — an
    approval decision. ``NOTIFICATION`` — a notification event. ``SYSTEM`` — system
    knowledge. Kept as a ``str`` enum so each serialises to its label.
    """

    USER_PREFERENCE = "USER_PREFERENCE"
    WORKFLOW = "WORKFLOW"
    TASK_RESULT = "TASK_RESULT"
    APPROVAL = "APPROVAL"
    NOTIFICATION = "NOTIFICATION"
    SYSTEM = "SYSTEM"


class MemoryImportance(str, Enum):
    """The allowed, deterministic importance levels of a memory.

    ``TEMPORARY`` — short-lived, discardable. ``SHORT_TERM`` — kept for a while.
    ``LONG_TERM`` — kept indefinitely under normal use. ``PERMANENT`` — never
    forgotten by policy. The mapping from category to importance lives in the
    *configurable* classifier, not here. Kept as a ``str`` enum so each serialises
    to its label.
    """

    TEMPORARY = "TEMPORARY"
    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    PERMANENT = "PERMANENT"


# Deterministic ordering of the importance levels (temporary → permanent). Kept
# beside the enum so every consumer ranks importance identically.
IMPORTANCE_ORDER: Dict[MemoryImportance, int] = {
    MemoryImportance.TEMPORARY: 0,
    MemoryImportance.SHORT_TERM: 1,
    MemoryImportance.LONG_TERM: 2,
    MemoryImportance.PERMANENT: 3,
}


class MemoryRecord(BaseModel):
    """Immutable record of one remembered piece of information (no execution).

    ``frozen=True`` makes instances immutable, so an update produces a new instance.
    ``memory_id`` is the deterministic handle; ``workflow_id`` links the memory to a
    workflow instance (empty for non-workflow memories); ``category`` is one of the
    :class:`MemoryCategory` labels; ``importance`` is the classified
    :class:`MemoryImportance`; ``content`` is the remembered text; ``tags`` are
    plain filter labels; ``created_at_sequence`` is the deterministic ordinal (never
    a clock); ``persisted_version`` is the Persistence Layer version of the
    associated workflow instance (``None`` when no workflow state was persisted);
    and ``metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    memory_id: _NonEmptyStr
    workflow_id: str = ""
    category: MemoryCategory
    importance: MemoryImportance
    content: str = ""
    tags: List[str] = Field(default_factory=list)
    created_at_sequence: int = Field(default=0, ge=0)
    persisted_version: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryDecision(BaseModel):
    """Immutable decision about whether to remember information (no execution).

    ``frozen=True`` makes instances immutable. ``workflow_id`` links the decision to
    a workflow (empty for non-workflow memories); ``category`` is the
    :class:`MemoryCategory` under review; ``should_remember`` is the policy verdict;
    ``importance`` is the classifier's :class:`MemoryImportance`; ``reason`` is a
    plain-text rationale; and ``decision_metadata`` carries plain descriptors.
    Producing this DTO runs nothing and stores nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: str = ""
    category: MemoryCategory
    should_remember: bool
    importance: MemoryImportance
    reason: str = ""
    decision_metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(BaseModel):
    """Immutable deterministic retrieval filter (no semantic search).

    ``frozen=True`` makes instances immutable. Each set field narrows the result:
    ``workflow_id`` (by workflow), ``category`` (by category), ``importance`` (by
    priority), and ``tag`` (by tag). ``latest`` orders newest-first; ``limit`` caps
    the count; and ``query_metadata`` carries plain descriptors. Every filter is an
    exact, deterministic match — there is no embedding, vector, or semantic scoring.
    Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: Optional[str] = None
    category: Optional[MemoryCategory] = None
    importance: Optional[MemoryImportance] = None
    tag: Optional[str] = None
    latest: bool = False
    limit: Optional[int] = Field(default=None, ge=1)
    query_metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySummary(BaseModel):
    """Immutable aggregate summary of matching memories (deterministic counts).

    ``frozen=True`` makes instances immutable. ``workflow_id`` is the scope (``None``
    for all); ``total`` is the count of summarised memories; ``by_category`` and
    ``by_importance`` are deterministic counts keyed by label; ``memory_ids`` are the
    summarised ids in retrieval order; and ``summary_metadata`` carries plain
    descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: Optional[str] = None
    total: int = Field(default=0, ge=0)
    by_category: Dict[str, int] = Field(default_factory=dict)
    by_importance: Dict[str, int] = Field(default_factory=dict)
    memory_ids: List[str] = Field(default_factory=list)
    summary_metadata: Dict[str, Any] = Field(default_factory=dict)
