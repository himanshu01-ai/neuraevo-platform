"""AI Employee package (Sprint 16.1 — the AI Employee Foundation).

Ships the foundation layer that owns employee sessions and task delegation and
*orchestrates* the existing systems (it plans nothing and executes nothing):

* the provider-independent, immutable DTOs — :class:`EmployeeProfile`,
  :class:`TaskDelegation`, :class:`EmployeeSession`, :class:`EmployeeContext`,
  and :class:`EmployeeExecutionResult`, plus the :class:`TaskPriority` and
  :class:`EmployeeSessionStatus` enums; and
* the :class:`AIEmployee` coordinator (session -> context -> Planning Engine ->
  Workflow Coordinator -> result).

The coordinator uses only the injected Sprint 13 :class:`PlanningEngine` and the
Sprint 15.15 :class:`WorkflowCoordinator` through their existing public
contracts; it never touches Runtime, Memory, Permission, or Capability internals
directly. This layer is strictly additive to — and leaves untouched — every
frozen sprint through 15.15.
"""

from app.services.ai_employee.ai_employee import AIEmployee
from app.services.ai_employee.models import (
    EmployeeContext,
    EmployeeExecutionResult,
    EmployeeProfile,
    EmployeeSession,
    EmployeeSessionStatus,
    TaskDelegation,
    TaskPriority,
)

__all__ = [
    "AIEmployee",
    "EmployeeProfile",
    "TaskDelegation",
    "TaskPriority",
    "EmployeeSession",
    "EmployeeSessionStatus",
    "EmployeeContext",
    "EmployeeExecutionResult",
]
