"""Agent Coordination Platform package (Sprint 16.9 — coordinate multiple AI Employees).

Adds the coordination layer that decides *which* AI Employee handles *which* work
and tracks their collaboration, while execution stays ``TaskDelegator -> AIEmployee
-> Planning Engine + Workflow Coordinator`` (it executes no workflow or capability
itself). It coordinates agent collaboration only — it implements no distributed
execution, networking, RPC, message broker, thread, or async loop. It follows the
flow ``AgentCoordinator -> {AgentRegistry, AgentResolver, CoordinationPolicy,
TaskDelegator, CollaborationContext}``:

* the immutable DTOs :class:`AgentProfile`, :class:`AgentTask`,
  :class:`DelegationResult`, :class:`CoordinationContext`, and
  :class:`CoordinationPolicyResult`, plus the :class:`AgentStatus` enum and the
  :class:`CoordinationError` family;
* the :class:`AgentRegistry` (the roster of available AI Employees);
* the configurable :class:`AgentResolver` (which agents are suitable, ranked);
* the :class:`CoordinationPolicy` abstraction with :class:`SingleAgentPolicy`,
  :class:`CollaborativePolicy`, and :class:`PriorityPolicy`;
* the :class:`TaskDelegator` (delegates the running to the :class:`AIEmployee`,
  never the Workflow Coordinator);
* the :class:`CollaborationContext` (the live collaboration ledger); and
* the :class:`AgentCoordinator` coordinator.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.8, and it imports no capability module, no Workflow Coordinator, no
repository, and no networking/threading/async facility.
"""

from app.services.ai_employee.coordination.collaboration import (
    CollaborationContext,
)
from app.services.ai_employee.coordination.coordinator import AgentCoordinator
from app.services.ai_employee.coordination.delegator import TaskDelegator
from app.services.ai_employee.coordination.models import (
    AgentNotFoundError,
    AgentProfile,
    AgentStatus,
    AgentTask,
    CoordinationContext,
    CoordinationError,
    CoordinationPolicyResult,
    DelegationResult,
    TaskNotFoundError,
)
from app.services.ai_employee.coordination.policy import (
    CollaborativePolicy,
    CoordinationPolicy,
    PriorityPolicy,
    SingleAgentPolicy,
)
from app.services.ai_employee.coordination.registry import AgentRegistry
from app.services.ai_employee.coordination.resolver import AgentResolver

__all__ = [
    # DTOs & enums & errors
    "AgentProfile",
    "AgentTask",
    "DelegationResult",
    "CoordinationContext",
    "CoordinationPolicyResult",
    "AgentStatus",
    "CoordinationError",
    "AgentNotFoundError",
    "TaskNotFoundError",
    # registry / resolver / policy / delegator / collaboration / coordinator
    "AgentRegistry",
    "AgentResolver",
    "CoordinationPolicy",
    "SingleAgentPolicy",
    "CollaborativePolicy",
    "PriorityPolicy",
    "TaskDelegator",
    "CollaborationContext",
    "AgentCoordinator",
]
