"""Workflow lifecycle rules (Sprint 18.3).

Pure, stateless policy: which statuses may follow which. Mirrors
``app.services.employee_lifecycle`` so the two domains answer lifecycle
questions the same way.

No session, no I/O, no persistence.
"""

from app.utils.constants import WorkflowStatus

# Where a workflow may go from each status.
#
# ARCHIVED is deliberately terminal here: leaving an archive is a *restore*,
# which is handled by the service rather than by an arbitrary status write —
# the same rule the employee domain follows.
_ALLOWED_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.DRAFT: frozenset(
        {WorkflowStatus.PUBLISHED, WorkflowStatus.ARCHIVED}
    ),
    WorkflowStatus.PUBLISHED: frozenset(
        {WorkflowStatus.DRAFT, WorkflowStatus.ARCHIVED}
    ),
    WorkflowStatus.ARCHIVED: frozenset(),
}

# Statuses an archived workflow can be restored to. A restore returns it to the
# bench, never straight back into publication.
RESTORABLE_STATUSES: frozenset[WorkflowStatus] = frozenset({WorkflowStatus.DRAFT})


def can_transition(current: WorkflowStatus, target: WorkflowStatus) -> bool:
    """Return ``True`` when ``current`` may move to ``target``.

    Staying put is always allowed, so an update that resends the current status
    is not an error.
    """
    if current == target:
        return True
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())


def allowed_transitions(current: WorkflowStatus) -> frozenset[WorkflowStatus]:
    """Every status ``current`` may move to, excluding itself."""
    return _ALLOWED_TRANSITIONS.get(current, frozenset())
