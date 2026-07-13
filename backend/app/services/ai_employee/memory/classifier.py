"""Memory classifier (Sprint 16.6 — determine memory importance, configurable).

Defines the :class:`MemoryClassifier` abstraction and its configurable default
:class:`RuleBasedMemoryClassifier`. A classifier determines the
:class:`MemoryImportance` of a piece of information from its category. The default
maps preferences and system knowledge to ``PERMANENT``, workflow and task results
to ``LONG_TERM``, approvals to ``SHORT_TERM``, and notifications to ``TEMPORARY``;
the mapping and fallback are configurable.

Classifiers are deterministic and stateless and classify only — they decide,
store, and execute nothing. Strictly additive to Sprints 1.x–16.5.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.services.ai_employee.memory.models import (
    MemoryCategory,
    MemoryImportance,
)


class MemoryClassifier(ABC):
    """Abstraction that determines the importance of a memory (no execution).

    An implementation answers ``classify`` for a :class:`MemoryCategory` (with
    optional content and metadata as context), returning a
    :class:`MemoryImportance`. Implementations must be deterministic and must not
    decide rememberability, store, or execute anything.
    """

    @abstractmethod
    def classify(
        self,
        category: MemoryCategory,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryImportance:
        """Return the importance for information of ``category``."""


class RuleBasedMemoryClassifier(MemoryClassifier):
    """Configurable rule-based classifier — maps categories to importance levels.

    Constructed with an optional ``mapping`` override (merged over the default) and
    an optional ``default_importance`` fallback for unmapped categories (defaults to
    ``SHORT_TERM``). ``classify`` is a deterministic lookup. Stateless; it classifies
    only.
    """

    _DEFAULT_MAPPING = {
        MemoryCategory.USER_PREFERENCE: MemoryImportance.PERMANENT,
        MemoryCategory.SYSTEM: MemoryImportance.PERMANENT,
        MemoryCategory.WORKFLOW: MemoryImportance.LONG_TERM,
        MemoryCategory.TASK_RESULT: MemoryImportance.LONG_TERM,
        MemoryCategory.APPROVAL: MemoryImportance.SHORT_TERM,
        MemoryCategory.NOTIFICATION: MemoryImportance.TEMPORARY,
    }

    def __init__(
        self,
        mapping: Optional[Dict[MemoryCategory, MemoryImportance]] = None,
        default_importance: MemoryImportance = MemoryImportance.SHORT_TERM,
    ) -> None:
        self._mapping: Dict[MemoryCategory, MemoryImportance] = {
            **self._DEFAULT_MAPPING,
            **(mapping or {}),
        }
        self._default_importance = default_importance

    def classify(
        self,
        category: MemoryCategory,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryImportance:
        """Return the mapped importance for ``category`` (fallback for unmapped)."""
        return self._mapping.get(category, self._default_importance)
