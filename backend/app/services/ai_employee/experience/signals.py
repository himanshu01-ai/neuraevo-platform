"""Experience signals (Sprint 16.12 — read observed task state deterministically).

Small, pure helper functions that read *experience signals* from an observed frozen
Sprint 16.10 :class:`TaskStatusResponse` — the platform's window onto real task
activity. Each task carries a provider-independent ``result_summary`` and
``response_metadata`` descriptor bag; these helpers read named descriptors from them
with deterministic fallbacks, so the analyzers never reach past the service's public
surface and never assume a descriptor is present.

The frozen service always records ``workflow_status`` and ``planned_step_count`` on a
delegated task, so success, completion, and execution size are always observable;
richer descriptors (capability, feature, retries, approval/recovery, acceptance)
populate these signals when the observed task carries them and default safely
otherwise. These are pure reads: they compute, observe, and execute nothing, and they
import no capability, workflow coordinator, provider, or SDK. Strictly additive to
Sprints 1.x–16.11, whose modules are left untouched.
"""

from typing import Any, List, Optional

from app.services.ai_employee.service import TaskState, TaskStatusResponse

# Descriptor keys read from a task's ``result_summary`` / ``response_metadata``.
CAPABILITY_KEY = "capability"
FEATURE_KEY = "feature"
WORKFLOW_KEY = "workflow"
RETRY_COUNT_KEY = "retry_count"
APPROVAL_REQUIRED_KEY = "approval_required"
RECOVERY_REQUIRED_KEY = "recovery_required"
GOAL_ACHIEVED_KEY = "goal_achieved"
OUTPUT_ACCEPTED_KEY = "output_accepted"
ABANDONED_KEY = "abandoned"
WORKFLOW_STATUS_KEY = "workflow_status"

# The workflow-status label the frozen Workflow Coordinator reports on success. Kept
# as a local literal so this module imports no runtime/workflow package.
_WORKFLOW_COMPLETED = "COMPLETED"

# Execution-size descriptor keys, in preference order (a deterministic duration proxy).
_STEP_KEYS = (
    "executed_step_count",
    "planned_step_count",
    "total_step_count",
    "step_count",
)


def _read(task: TaskStatusResponse, key: str, default: Any) -> Any:
    """Return ``key`` from the task's summary, then metadata, else ``default``."""
    if key in task.result_summary:
        return task.result_summary[key]
    if key in task.response_metadata:
        return task.response_metadata[key]
    return default


def _read_str(task: TaskStatusResponse, key: str) -> str:
    """Return a trimmed string descriptor (empty when absent or blank)."""
    value = _read(task, key, "")
    return str(value).strip() if value is not None else ""


def _read_int(task: TaskStatusResponse, key: str, default: int = 0) -> int:
    """Return a non-negative integer descriptor (``default`` when absent/invalid)."""
    value = _read(task, key, default)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def _read_bool(
    task: TaskStatusResponse, key: str, default: bool = False
) -> bool:
    """Return a boolean descriptor (``default`` when absent)."""
    value = _read(task, key, default)
    return bool(value)


# --- identity signals ----------------------------------------------------
def capability(task: TaskStatusResponse) -> str:
    """Return the capability name the task exercised (empty when unknown)."""
    return _read_str(task, CAPABILITY_KEY)


def feature(task: TaskStatusResponse) -> str:
    """Return the feature name the task exercised (empty when unknown)."""
    return _read_str(task, FEATURE_KEY)


def workflow(task: TaskStatusResponse) -> str:
    """Return the workflow name the task exercised (empty when unknown)."""
    return _read_str(task, WORKFLOW_KEY)


# --- outcome signals -----------------------------------------------------
def succeeded(task: TaskStatusResponse) -> bool:
    """Return whether the task completed successfully (the frozen ``success`` flag)."""
    return bool(task.success)


def workflow_completed(task: TaskStatusResponse) -> bool:
    """Return whether the task's workflow reported completion.

    Reads the frozen ``workflow_status`` descriptor when present; otherwise falls back
    to the task's terminal ``COMPLETED`` state.
    """
    status = _read_str(task, WORKFLOW_STATUS_KEY)
    if status:
        return status == _WORKFLOW_COMPLETED
    return task.state == TaskState.COMPLETED


def execution_units(task: TaskStatusResponse) -> int:
    """Return the task's deterministic execution size (a step-count duration proxy)."""
    for key in _STEP_KEYS:
        value = _read(task, key, None)
        if value is not None:
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if number >= 0:
                return number
    return 0


def retry_count(task: TaskStatusResponse) -> int:
    """Return how many retries the task incurred (``0`` when unknown)."""
    return _read_int(task, RETRY_COUNT_KEY, 0)


def approval_required(task: TaskStatusResponse) -> bool:
    """Return whether the task required human approval (``False`` when unknown)."""
    return _read_bool(task, APPROVAL_REQUIRED_KEY, False)


def recovery_required(task: TaskStatusResponse) -> bool:
    """Return whether the task required recovery (``False`` when unknown)."""
    return _read_bool(task, RECOVERY_REQUIRED_KEY, False)


def goal_achieved(task: TaskStatusResponse) -> bool:
    """Return whether the task achieved its goal (defaults to its success flag)."""
    return _read_bool(task, GOAL_ACHIEVED_KEY, succeeded(task))


def output_accepted(task: TaskStatusResponse) -> bool:
    """Return whether the task's output was accepted (defaults to its success flag)."""
    return _read_bool(task, OUTPUT_ACCEPTED_KEY, succeeded(task))


def cancelled(task: TaskStatusResponse) -> bool:
    """Return whether the task was cancelled."""
    return task.state == TaskState.CANCELLED


def abandoned(task: TaskStatusResponse) -> bool:
    """Return whether the task was abandoned (explicit flag, or left paused)."""
    return _read_bool(task, ABANDONED_KEY, False) or (
        task.state == TaskState.PAUSED
    )


def failed(task: TaskStatusResponse) -> bool:
    """Return whether the task failed."""
    return task.state == TaskState.FAILED


def resolve_tasks(
    service, tasks: Optional[List[TaskStatusResponse]]
) -> List[TaskStatusResponse]:
    """Return ``tasks`` when supplied, else the service's observed task list.

    Callers pass an explicit task list to analyse a specific observation set; when
    omitted the analyzers observe the live service surface via ``list_tasks()``.
    """
    if tasks is not None:
        return list(tasks)
    return list(service.list_tasks())
