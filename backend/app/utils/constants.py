"""Shared enumerations and constants."""

from enum import Enum


class MemoryType(str, Enum):
    """Categories of employee memory.

    - ``permanent``: long-lived facts that should always be retained.
    - ``working``: short-lived context for the current activity.
    - ``learned``: information inferred from interactions over time.
    """

    PERMANENT = "permanent"
    WORKING = "working"
    LEARNED = "learned"


class SessionStatus(str, Enum):
    """Lifecycle status of an interview session.

    - ``created``: session created but not yet started.
    - ``in_progress``: session underway.
    - ``completed``: session finished.
    """

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
