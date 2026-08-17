"""Failure classifier (Sprint 16.8 — classify failures, configurable).

Defines the :class:`FailureClassifier` abstraction and its configurable default
:class:`RuleBasedFailureClassifier`. A classifier maps a plain-text failure reason
to a :class:`FailureType` — ``TRANSIENT``, ``PERMANENT``, ``USER_ACTION``,
``SYSTEM``, or ``UNKNOWN``. The default matches configurable keyword rules (e.g.
"timeout" -> ``TRANSIENT``, "invalid" -> ``PERMANENT``, "approval" -> ``USER_ACTION``,
"internal" -> ``SYSTEM``) and falls back to ``UNKNOWN``.

Classifiers are deterministic and stateless and classify only — they decide,
retry, and execute nothing. Strictly additive to Sprints 1.x–16.7.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.services.ai_employee.recovery.models import FailureType


class FailureClassifier(ABC):
    """Abstraction that classifies a failure reason into a :class:`FailureType`.

    An implementation answers ``classify`` for a plain-text reason (with optional
    metadata as context). Implementations must be deterministic and must not decide
    recovery, retry, or execute anything.
    """

    @abstractmethod
    def classify(
        self, reason: str, metadata: Optional[Dict[str, Any]] = None
    ) -> FailureType:
        """Return the :class:`FailureType` for a failure ``reason``."""


class RuleBasedFailureClassifier(FailureClassifier):
    """Configurable keyword classifier — maps reason keywords to failure types.

    Constructed with an optional ``rules`` override map (keyword -> type, merged over
    the default) and an optional ``default_type`` fallback (defaults to ``UNKNOWN``).
    ``classify`` returns the type of the first matching keyword (case-insensitive
    substring) in rule order, else the default. Deterministic and stateless.
    """

    _DEFAULT_RULES = {
        "timeout": FailureType.TRANSIENT,
        "unavailable": FailureType.TRANSIENT,
        "rate limit": FailureType.TRANSIENT,
        "temporar": FailureType.TRANSIENT,
        "invalid": FailureType.PERMANENT,
        "not found": FailureType.PERMANENT,
        "permission": FailureType.PERMANENT,
        "forbidden": FailureType.PERMANENT,
        "approval": FailureType.USER_ACTION,
        "user": FailureType.USER_ACTION,
        "manual": FailureType.USER_ACTION,
        "internal": FailureType.SYSTEM,
        "system": FailureType.SYSTEM,
        "crash": FailureType.SYSTEM,
    }

    def __init__(
        self,
        rules: Optional[Dict[str, FailureType]] = None,
        default_type: FailureType = FailureType.UNKNOWN,
    ) -> None:
        # Preserve rule order (first match wins): defaults first, then overrides.
        self._rules: Dict[str, FailureType] = {
            **self._DEFAULT_RULES,
            **(rules or {}),
        }
        self._default_type = default_type

    def classify(
        self, reason: str, metadata: Optional[Dict[str, Any]] = None
    ) -> FailureType:
        """Return the type of the first matching keyword, else the default."""
        lowered = (reason or "").lower()
        for keyword, failure_type in self._rules.items():
            if keyword in lowered:
                return failure_type
        return self._default_type
