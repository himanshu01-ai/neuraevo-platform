"""Release helpers (Sprint 16.15 — deterministic issue/status construction).

Small, pure factory helpers shared by the release components to build immutable
:class:`ReleaseIssue` s and to fold a list of issues into a :class:`ReleaseStatus`.
Centralising the pass rule keeps every release check consistent: any ``BLOCKER`` issue
fails the check, while ``WARNING``/``INFO`` issues are surfaced without blocking.

These are pure functions: they build DTOs only and decide, delegate, and execute
nothing. Strictly additive to Sprints 1.x–16.14, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.release.models import (
    ReleaseIssue,
    ReleaseSeverity,
    ReleaseStatus,
)


def issue(
    issue_id: str,
    message: str,
    severity: ReleaseSeverity = ReleaseSeverity.BLOCKER,
    area: str = "",
    detail: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ReleaseIssue:
    """Build an immutable :class:`ReleaseIssue` (defaults to ``BLOCKER`` severity)."""
    return ReleaseIssue(
        issue_id=issue_id,
        severity=severity,
        area=area,
        message=message,
        detail=detail,
        issue_metadata=dict(metadata or {}),
    )


def status(
    name: str,
    issues: List[ReleaseIssue],
    detail: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ReleaseStatus:
    """Fold ``issues`` into a :class:`ReleaseStatus` (fails on any ``BLOCKER``)."""
    blocked = blockers(issues)
    return ReleaseStatus(
        name=name,
        passed=not blocked,
        issues=list(issues),
        detail=detail or ("passed" if not blocked else "blocked"),
        status_metadata=dict(metadata or {}),
    )


def blockers(issues: List[ReleaseIssue]) -> List[ReleaseIssue]:
    """Return only the ``BLOCKER``-severity issues in ``issues``."""
    return [i for i in issues if i.severity == ReleaseSeverity.BLOCKER]
