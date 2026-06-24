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
