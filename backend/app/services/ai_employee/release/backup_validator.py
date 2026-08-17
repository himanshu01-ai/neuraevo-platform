"""Backup validator (Sprint 16.15 — validate snapshot backup/restore integrity).

Defines :class:`BackupValidator`, which validates that the backend's state is
reproducible and safely serialisable for backup — backup integrity, restore integrity,
and snapshot consistency — by *reading* a deterministic state snapshot from the frozen
Sprint 16.14 :class:`DeveloperDashboardManager`. It never executes a workflow, changes
behaviour, or modifies state, and it writes to no store.

"Backup" here means serialising an immutable state snapshot; "restore" means loading it
back losslessly; "snapshot consistency" means two snapshots of unchanged state are
identical. All three are pure, in-memory checks over frozen DTOs — there is no external
backup system, database, or file. It observes only: it validates and executes,
delegates, and stores nothing. Strictly additive to Sprints 1.x–16.14, whose modules are
left untouched.
"""

from typing import List

from app.services.ai_employee.release import common
from app.services.ai_employee.release.models import (
    BackupReport,
    ReleaseIssue,
)


class BackupValidator:
    """Validates snapshot backup/restore integrity in memory (read-only, no store).

    Constructed with an injected :class:`DeveloperDashboardManager` (constructor
    injection; it instantiates none). ``validate`` takes a deterministic overview
    snapshot, serialises it, reloads it, and takes a second snapshot to confirm
    consistency, returning a :class:`BackupReport`. It writes to no store and runs
    nothing.
    """

    def __init__(self, dashboard) -> None:
        self.dashboard = dashboard

    def validate(self) -> BackupReport:
        """Return the :class:`BackupReport` for the state snapshot round-trip."""
        first = self.dashboard.overview()
        second = self.dashboard.overview()
        snapshot_consistency = first == second

        dumped = first.model_dump()
        backup_integrity = isinstance(dumped, dict) and bool(dumped)

        try:
            restored = type(first).model_validate(dumped)
            restore_integrity = restored == first
        except Exception:  # noqa: BLE001 - a failed round-trip is a blocker below
            restore_integrity = False

        issues: List[ReleaseIssue] = []
        if not backup_integrity:
            issues.append(
                common.issue(
                    issue_id="backup-integrity",
                    message="state snapshot did not serialise",
                    area="backup",
                )
            )
        if not restore_integrity:
            issues.append(
                common.issue(
                    issue_id="backup-restore",
                    message="state snapshot did not round-trip losslessly",
                    area="backup",
                )
            )
        if not snapshot_consistency:
            issues.append(
                common.issue(
                    issue_id="backup-snapshot",
                    message="two snapshots of unchanged state differ",
                    area="backup",
                )
            )

        return BackupReport(
            ok=not common.blockers(issues),
            backup_integrity=backup_integrity,
            restore_integrity=restore_integrity,
            snapshot_consistency=snapshot_consistency,
            issues=issues,
            backup_metadata={"snapshot": "dashboard.overview"},
        )
