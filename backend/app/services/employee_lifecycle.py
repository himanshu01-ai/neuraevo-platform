"""Employee lifecycle rules (Sprint 18.2A).

Pure, stateless policy: which statuses may follow which. Kept out of the
service so the rules can be read and tested on their own, and so there is one
place that decides whether a transition is legal.

No session, no I/O, no persistence.
"""

from app.utils.constants import EmployeeStatus

# Where an employee may go from each status.
#
# ARCHIVED is deliberately terminal here: leaving an archive is a *restore*,
# which returns the employee to the status it held beforehand and is handled by
# the service rather than by an arbitrary status write. ERROR is reported by
# the platform, so nothing transitions *into* it by request.
_ALLOWED_TRANSITIONS: dict[EmployeeStatus, frozenset[EmployeeStatus]] = {
    EmployeeStatus.DRAFT: frozenset(
        {EmployeeStatus.READY, EmployeeStatus.ARCHIVED}
    ),
    EmployeeStatus.READY: frozenset(
        {
            EmployeeStatus.DRAFT,
            EmployeeStatus.ACTIVE,
            EmployeeStatus.PAUSED,
            EmployeeStatus.ARCHIVED,
        }
    ),
    EmployeeStatus.ACTIVE: frozenset(
        {EmployeeStatus.PAUSED, EmployeeStatus.READY, EmployeeStatus.ARCHIVED}
    ),
    EmployeeStatus.PAUSED: frozenset(
        {EmployeeStatus.ACTIVE, EmployeeStatus.READY, EmployeeStatus.ARCHIVED}
    ),
    EmployeeStatus.ARCHIVED: frozenset(),
    EmployeeStatus.ERROR: frozenset(
        {EmployeeStatus.DRAFT, EmployeeStatus.READY, EmployeeStatus.ARCHIVED}
    ),
}

# Statuses an archived employee can be restored to. A restore never puts an
# employee straight back into service — it returns it to the bench.
RESTORABLE_STATUSES: frozenset[EmployeeStatus] = frozenset(
    {EmployeeStatus.DRAFT, EmployeeStatus.READY}
)


def can_transition(current: EmployeeStatus, target: EmployeeStatus) -> bool:
    """Return ``True`` when ``current`` may move to ``target``.

    Staying put is always allowed, so an update that resends the current status
    is not an error.
    """
    if current == target:
        return True
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())


def allowed_transitions(current: EmployeeStatus) -> frozenset[EmployeeStatus]:
    """Every status ``current`` may move to, excluding itself."""
    return _ALLOWED_TRANSITIONS.get(current, frozenset())

