"""Dashboard helpers (Sprint 16.14 — read subsystem status from operations).

Small, pure helper that reads the per-subsystem component status from the frozen Sprint
16.11 :class:`EnterpriseOperationsManager` (via its observability surface) into a
name -> ``ComponentStatus`` map, so the subsystem-focused inspectors (memory, scheduler,
recovery) report a consistent (present, healthy, state) projection.

This is a pure read: it builds a mapping only and decides, delegates, and executes
nothing. Strictly additive to Sprints 1.x–16.13, whose modules are left untouched.
"""

from typing import Dict


def component_map(operations) -> Dict[str, object]:
    """Return the subsystem name -> component-status map from the operations manager."""
    return {
        component.name: component
        for component in operations.observability.component_status()
    }
