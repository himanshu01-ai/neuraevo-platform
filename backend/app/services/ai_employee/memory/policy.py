"""Memory policy (Sprint 16.6 — decide whether information should be remembered).

Defines the :class:`MemoryPolicy` abstraction and its configurable default
:class:`RuleBasedMemoryPolicy`. A policy decides *whether* a piece of information
(by category) should be remembered — e.g. conversation, workflow result, approval,
notification, user preference, system knowledge. The default remembers everything
except transient notifications, and the rememberable set is configurable.

Policies are deterministic and stateless and decide only — they classify, store,
and execute nothing. Strictly additive to Sprints 1.x–16.5.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Optional

from app.services.ai_employee.memory.models import MemoryCategory


class MemoryPolicy(ABC):
    """Abstraction that decides whether information should be remembered.

    An implementation answers ``should_remember`` for a :class:`MemoryCategory`
    (with optional content and metadata as context). Implementations must be
    deterministic and must not classify, store, or execute anything; the
    orchestrator acts on the verdict.
    """

    @abstractmethod
    def should_remember(
        self,
        category: MemoryCategory,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Return whether information of ``category`` should be remembered."""


class RuleBasedMemoryPolicy(MemoryPolicy):
    """Configurable rule-based policy — remembers a configurable set of categories.

    Constructed with an optional ``rememberable`` set of categories (default: every
    category except :attr:`MemoryCategory.NOTIFICATION`, which is transient).
    ``should_remember`` is a deterministic set-membership test. Stateless; it
    decides only.
    """

    _DEFAULT_REMEMBERABLE = frozenset(
        {
            MemoryCategory.USER_PREFERENCE,
            MemoryCategory.WORKFLOW,
            MemoryCategory.TASK_RESULT,
            MemoryCategory.APPROVAL,
            MemoryCategory.SYSTEM,
        }
    )

    def __init__(
        self, rememberable: Optional[Iterable[MemoryCategory]] = None
    ) -> None:
        self._rememberable = (
            frozenset(rememberable)
            if rememberable is not None
            else self._DEFAULT_REMEMBERABLE
        )

    def should_remember(
        self,
        category: MemoryCategory,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Return whether ``category`` is in the configured rememberable set."""
        return category in self._rememberable
