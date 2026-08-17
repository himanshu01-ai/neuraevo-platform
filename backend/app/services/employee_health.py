"""Employee health derivation (Sprint 18.2A).

Health here is a *statement about stored configuration*, not a measurement.
Nothing is sampled, timed, pinged, or estimated — every answer follows from
facts already in the database, so the same employee always yields the same
health. That is deliberate: a fabricated uptime or latency number would be
worse than no number at all.

Pure and stateless: no session, no I/O.
"""

from dataclasses import dataclass, field

from app.models.employee import Employee
from app.utils.constants import (
    EmployeeCapability,
    EmployeeHealth,
    EmployeeStatus,
    PermissionLevel,
)

# Which capability each permission depends on. A permission granted above
# BLOCKED without its capability is a configuration the platform could not
# honour, so it counts against health.
PERMISSION_REQUIRES: dict[str, EmployeeCapability] = {
    "read_memory": EmployeeCapability.MEMORY,
    "write_memory": EmployeeCapability.MEMORY,
    "browse_web": EmployeeCapability.BROWSER,
    "run_code": EmployeeCapability.PYTHON,
    "modify_files": EmployeeCapability.FILES,
    "send_email": EmployeeCapability.EMAIL,
    "schedule_events": EmployeeCapability.CALENDAR,
    "request_approval": EmployeeCapability.APPROVAL,
}


@dataclass(frozen=True)
class EmployeeHealthReport:
    """Health plus the reasons behind it.

    The reasons are the point: a bare label tells an operator nothing they can
    act on, so every judgement names the stored fact that produced it.
    """

    state: EmployeeHealth
    reasons: list[str] = field(default_factory=list)


def derive_health(employee: Employee) -> EmployeeHealthReport:
    """Report an employee's health from its stored state."""
    status = _status_of(employee)

    if status is EmployeeStatus.ERROR:
        return EmployeeHealthReport(
            EmployeeHealth.UNHEALTHY,
            ["The platform reported an error for this employee."],
        )

    # An archived or never-finished employee isn't in service, so there is
    # nothing to be healthy or unhealthy about. UNKNOWN says exactly that.
    if status is EmployeeStatus.ARCHIVED:
        return EmployeeHealthReport(
            EmployeeHealth.UNKNOWN, ["This employee is archived."]
        )
    if status is EmployeeStatus.DRAFT:
        return EmployeeHealthReport(
            EmployeeHealth.UNKNOWN,
            ["This employee is still a draft and has not been put into service."],
        )

    reasons: list[str] = []
    held = {grant.capability for grant in employee.capabilities}

    if not held:
        reasons.append("No capabilities are granted, so it cannot do anything yet.")

    for grant in employee.permissions:
        if grant.level == PermissionLevel.BLOCKED.value:
            continue
        required = PERMISSION_REQUIRES.get(grant.permission)
        if required is not None and required.value not in held:
            reasons.append(
                f"Permission '{grant.permission}' needs the "
                f"'{required.value}' capability, which is not granted."
            )

    if reasons:
        return EmployeeHealthReport(EmployeeHealth.DEGRADED, reasons)

    return EmployeeHealthReport(
        EmployeeHealth.HEALTHY, ["Configuration is complete and consistent."]
    )


def _status_of(employee: Employee) -> EmployeeStatus:
    try:
        return EmployeeStatus(employee.status)
    except ValueError:
        # A status this build doesn't recognise is not something to guess at.
        return EmployeeStatus.DRAFT

