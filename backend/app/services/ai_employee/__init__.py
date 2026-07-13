"""AI Employee package (Sprint 16.1 Foundation + Sprint 16.2 Execution Platform).

Sprint 16.1 — the AI Employee Foundation:

* the immutable DTOs :class:`EmployeeProfile`, :class:`TaskDelegation`,
  :class:`EmployeeSession`, :class:`EmployeeContext`, and
  :class:`EmployeeExecutionResult`, plus the :class:`TaskPriority` and
  :class:`EmployeeSessionStatus` enums; and
* the :class:`AIEmployee` coordinator (session -> context -> Planning Engine ->
  Workflow Coordinator -> result).

Sprint 16.2 — the AI Employee Execution Platform (the lifecycle of a delegated
job):

* the immutable DTOs :class:`WorkflowInstance`, :class:`WorkflowLifecycleState`,
  :class:`WorkflowProgress`, :class:`WorkflowNotification`,
  :class:`ApprovalDecision`, and :class:`WorkflowSnapshot`, plus the
  :class:`WorkflowLifecycleStatus`, :class:`WorkflowProgressStatus`, and
  :class:`WorkflowNotificationEvent` enums and the :class:`WorkflowLifecycleError`;
* the :class:`WorkflowLifecycleManager` coordinator; and
* the extensible managers — :class:`ProgressTracker`, the :class:`ApprovalManager`
  abstraction with :class:`AutoApprovalPolicy`, the :class:`NotificationManager`
  abstraction with :class:`InMemoryNotificationManager`, the
  :class:`RecoveryManager` abstraction with :class:`BasicRecoveryManager`, and the
  :class:`PersistenceManager` abstraction with :class:`InMemoryPersistenceManager`.

Both layers use only the injected Sprint 13 :class:`PlanningEngine` and the Sprint
15.15 :class:`WorkflowCoordinator` through their existing public contracts; they
never touch Runtime, Memory, Permission, or Capability internals directly and
never import a capability module. This package is strictly additive to — and
leaves untouched — every frozen sprint through 16.1.
"""

from app.services.ai_employee.ai_employee import AIEmployee
from app.services.ai_employee.approval_manager import (
    ApprovalManager,
    AutoApprovalPolicy,
)
from app.services.ai_employee.models import (
    EmployeeContext,
    EmployeeExecutionResult,
    EmployeeProfile,
    EmployeeSession,
    EmployeeSessionStatus,
    TaskDelegation,
    TaskPriority,
)
from app.services.ai_employee.notification_manager import (
    InMemoryNotificationManager,
    NotificationManager,
)
from app.services.ai_employee.persistence_manager import (
    InMemoryPersistenceManager,
    PersistenceManager,
)
from app.services.ai_employee.platform_models import (
    ApprovalDecision,
    WorkflowInstance,
    WorkflowLifecycleError,
    WorkflowLifecycleState,
    WorkflowLifecycleStatus,
    WorkflowNotification,
    WorkflowNotificationEvent,
    WorkflowProgress,
    WorkflowProgressStatus,
    WorkflowSnapshot,
)
from app.services.ai_employee.progress_tracker import ProgressTracker
from app.services.ai_employee.recovery_manager import (
    BasicRecoveryManager,
    RecoveryManager,
)
from app.services.ai_employee.workflow_lifecycle_manager import (
    WorkflowLifecycleManager,
)

__all__ = [
    # Sprint 16.1 — Foundation
    "AIEmployee",
    "EmployeeProfile",
    "TaskDelegation",
    "TaskPriority",
    "EmployeeSession",
    "EmployeeSessionStatus",
    "EmployeeContext",
    "EmployeeExecutionResult",
    # Sprint 16.2 — Execution Platform DTOs
    "WorkflowInstance",
    "WorkflowLifecycleState",
    "WorkflowLifecycleStatus",
    "WorkflowProgress",
    "WorkflowProgressStatus",
    "WorkflowNotification",
    "WorkflowNotificationEvent",
    "ApprovalDecision",
    "WorkflowSnapshot",
    "WorkflowLifecycleError",
    # Sprint 16.2 — coordinator + managers
    "WorkflowLifecycleManager",
    "ProgressTracker",
    "ApprovalManager",
    "AutoApprovalPolicy",
    "NotificationManager",
    "InMemoryNotificationManager",
    "RecoveryManager",
    "BasicRecoveryManager",
    "PersistenceManager",
    "InMemoryPersistenceManager",
]
